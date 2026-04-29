"""POST /api/llm/generate-story — server-owned story generation.

Why this is a dedicated endpoint
--------------------------------
Mobile shouldn't be picking the model. Mobile shouldn't be shipping a
copy of the system prompt either — that means a typo or improvement
needs an app store release. This endpoint owns:

  - the model (Gemini 2.5 Flash; Sarvam-30b on fallback)
  - the system prompt
  - max_tokens, temperature, reasoning settings
  - post-processing (Odia digit normalization, purna virama spacing)

Mobile sends only what it has: the reporter's raw notes. The server
returns the polished article body and the name of the model that served
it (so we can see in logs/UI when the fallback fired).

Fallback chain
--------------
1. Try Gemini 2.5 Flash (faithful to facts, obeys structure, ~3-4×
   cheaper than Claude Haiku at parity quality on Odia journalism).
2. On TRANSIENT failure (timeout, 5xx, 429, network error) →
   fall back to Sarvam-30b with the same system prompt.
3. On NON-TRANSIENT Gemini failure (400/401/403): bubble up. Those
   are deploy/auth bugs and silent fallback would mask them forever.
4. On Sarvam failure after fallback: 502 to client.

Migrated from Anthropic Claude Haiku → Gemini 2.5 Flash on
2026-04-29; Sarvam stays as a safety net only.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel, Field

from ..deps import get_current_user
from ..models.user import User
from ..services import gemini_client, sarvam_client
from ..services.gemini_client import GeminiError, is_transient_error

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# System prompt — single source of truth. Was previously a string constant
# in mobile/lib/features/create_news/providers/create_news_provider.dart;
# moved here so prompt tweaks ship as a backend deploy, not an APK release.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a senior Odia news editor. The reporter has dictated "
    "or typed raw notes for a news story — the dictation may contain "
    "English words that slipped in instead of Odia, duplicate phrases, "
    "wrong punctuation, hesitations, and false starts. Your job is to "
    "REFINE these notes into a publishable Odia article body WITHOUT "
    "ALTERING THE STORY (no new facts, no removed facts).\n"
    "\n"
    "Structure:\n"
    "1. Lead paragraph: who/what/when/where, in 1-2 sentences.\n"
    "2. Follow with supporting paragraphs in logical order.\n"
    "3. Separate paragraphs with a blank line. Keep it tight — "
    "newspapers, not blog posts.\n"
    "\n"
    "Language & script:\n"
    "4. Use clean Odia, proper purna virama (।), and Odia numerals "
    "(୦-୯).\n"
    "5. ENGLISH-SCRIPT SLIPS — the reporter may dictate proper nouns "
    "in English script (Nayagarh, Shree Jagannath, Mahaprabhu, place "
    "and person names, etc.). Render them in proper Odia script "
    "(ନୟାଗଡ଼, ଶ୍ରୀଜଗନ୍ନାଥ, ମହାପ୍ରଭୁ). Do the same for any English "
    "common nouns or phrases that slipped in — write the Odia "
    "equivalent. The output must be entirely in Odia script.\n"
    "6. PRESERVE FACTS — names, places, organisations, designations, "
    "numbers, dates, quotes: keep the exact substance the reporter "
    "gave. Do NOT invent, swap, or 'correct' them; only render their "
    "script/spelling consistently. If the same name appears with "
    "different spellings, use one consistent Odia rendering "
    "throughout.\n"
    "\n"
    "Cleanup:\n"
    "7. Strip dictation artifacts: hesitations (ahh, umm, ehi… ehi…), "
    "discourse markers (matlab, yaani, haan, to, achha, bujhilen, "
    "kahibaaku gale, thik achi), false starts.\n"
    "8. Collapse duplicate phrases caused by dictation (e.g. "
    "\"ଲକ୍ଷ ଲକ୍ଷ ଟଙ୍କା । ରାଜସ୍ୱ ହାନି । ଲକ୍ଷ ଲକ୍ଷ ଟଙ୍କା ।\" → "
    "\"ଲକ୍ଷ ଲକ୍ଷ ଟଙ୍କାର ରାଜସ୍ୱ ହାନି ।\"). Write like an editor, not a "
    "transcriber.\n"
    "9. Fix punctuation — proper purna virama placement, no stray "
    "fragments, no broken sentences.\n"
    "\n"
    "Return ONLY the article body. No headline, no byline, no "
    "commentary, no preamble like \"Here is the refined version\"."
)

# Model picks (centralized so a future swap is one constant change).
# Migrated from Anthropic Claude Haiku → Gemini 2.5 Flash on
# 2026-04-29 after a sample bake-off showed Flash matched Haiku on
# Odia journalistic faithfulness at ~3-4× lower cost. Sarvam-30b
# stays as the safety-net fallback.
PRIMARY_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "sarvam-30b"

PRIMARY_MAX_TOKENS = 4096
FALLBACK_MAX_TOKENS = 8192


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class GenerateStoryRequest(BaseModel):
    notes: str = Field(
        ...,
        min_length=1,
        max_length=20_000,
        description="Reporter's raw dictated/typed notes. Server attaches "
        "the system prompt; client must NOT include any prompt scaffolding.",
    )
    story_id: Optional[str] = Field(
        default=None,
        description="Optional story UUID for cost attribution. When provided, "
        "the LLM call cost is charged to this story in the ledger.",
    )


class GenerateStoryResponse(BaseModel):
    body: str = Field(..., description="Polished Odia article body.")
    model: str = Field(
        ...,
        description="Which model actually served the response. Useful for "
        "monitoring fallback rate. One of 'gemini-2.5-flash' (primary) "
        "or 'sarvam-30b' (fallback).",
    )
    fallback_used: bool = Field(
        default=False,
        description="True when Gemini failed and Sarvam served. Surface "
        "in panel logs / debug overlays; not user-facing.",
    )


# ---------------------------------------------------------------------------
# Post-processing — same fixes the mobile used to apply on the response
# ---------------------------------------------------------------------------


_ASCII_TO_ODIA_DIGITS = str.maketrans({
    "0": "୦", "1": "୧", "2": "୨", "3": "୩", "4": "୪",
    "5": "୫", "6": "୬", "7": "୭", "8": "୮", "9": "୯",
})

# Match a danda that has no whitespace before it. We add one so the
# typography reads correctly (Odia convention: space before purna virama).
_UNSPACED_DANDA = re.compile(r"(?<!\s)।")


def _post_process(body: str) -> str:
    """Normalize Roman digits to Odia digits and ensure ' ।' spacing.

    Same two transformations the mobile client used to apply post-Sarvam.
    Now done server-side so any future caller (panel, internal tools) gets
    the same hygiene without re-implementing it.
    """
    if not body:
        return body
    body = body.strip().translate(_ASCII_TO_ODIA_DIGITS)
    body = _UNSPACED_DANDA.sub(" ।", body)
    return body


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/api/llm/generate-story", response_model=GenerateStoryResponse)
async def generate_story(
    body: GenerateStoryRequest,
    user: User = Depends(get_current_user),
) -> GenerateStoryResponse:
    """Polish raw reporter notes into a publishable Odia article body.

    The mobile app calls this when the reporter taps "Generate Story" in
    the notepad. The server picks the model and the prompt; the client
    is a thin passthrough.
    """
    notes = body.notes.strip()
    if not notes:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="notes is empty",
        )

    # Cost attribution — story_id when given, else generic generate_story
    # bucket. user_id is always set so we can answer "who burned the LLM
    # bill this week".
    attribution = (
        sarvam_client.cost_context(story_id=body.story_id, user_id=user.id)
        if body.story_id
        else sarvam_client.cost_context(bucket="generate_story", user_id=user.id)
    )

    # ── Try Gemini primary ──────────────────────────────────────────────
    with attribution:
        try:
            text = await gemini_client.chat(
                prompt=notes,
                system=SYSTEM_PROMPT,
                model=PRIMARY_MODEL,
                max_tokens=PRIMARY_MAX_TOKENS,
                temperature=0.3,
            )
            if not text:
                # Empty response is treated as a transient failure — fall
                # back to Sarvam rather than returning an empty body to the
                # user. Models occasionally emit only a refusal/empty turn.
                raise GeminiError(
                    "gemini returned empty content", status_code=None
                )
            return GenerateStoryResponse(
                body=_post_process(text),
                model=PRIMARY_MODEL,
                fallback_used=False,
            )
        except GeminiError as exc:
            if not is_transient_error(exc):
                logger.error(
                    "generate_story: non-transient Gemini failure "
                    "(status=%s, user=%s) — bubbling up: %s",
                    exc.status_code, user.id, exc,
                )
                raise HTTPException(
                    status_code=http_status.HTTP_502_BAD_GATEWAY,
                    detail=f"Gemini error ({exc.status_code}): {exc}",
                )
            logger.warning(
                "generate_story: Gemini transient failure "
                "(status=%s, user=%s, story_id=%s) — falling back to Sarvam: %s",
                exc.status_code, user.id, body.story_id, exc,
            )
            # Fall through to Sarvam fallback below

        # ── Sarvam fallback ───────────────────────────────────────────────
        try:
            sarvam_payload = {
                "model": FALLBACK_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": notes},
                ],
                "temperature": 0.3,
                "max_tokens": FALLBACK_MAX_TOKENS,
                # Sarvam-30b is a reasoning model. Without an explicit
                # effort setting it rambles in reasoning_content and the
                # actual body comes back truncated. "medium" matches
                # routers/sarvam.py /api/llm/chat for consistency.
                "reasoning_effort": "medium",
            }
            sarvam_data = await sarvam_client.chat(payload=sarvam_payload, timeout=60.0)
            text = _extract_sarvam_text(sarvam_data)
            if not text:
                logger.error(
                    "generate_story: Sarvam fallback returned empty content "
                    "(user=%s, story_id=%s) — both providers failed",
                    user.id, body.story_id,
                )
                raise HTTPException(
                    status_code=http_status.HTTP_502_BAD_GATEWAY,
                    detail="Both LLMs returned empty content",
                )
            return GenerateStoryResponse(
                body=_post_process(text),
                model=FALLBACK_MODEL,
                fallback_used=True,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — last-resort catch
            logger.error(
                "generate_story: Sarvam fallback also failed "
                "(user=%s, story_id=%s): %s",
                user.id, body.story_id, exc,
            )
            raise HTTPException(
                status_code=http_status.HTTP_502_BAD_GATEWAY,
                detail=f"Story generation failed (both providers): {exc}",
            )


def _extract_sarvam_text(data: dict) -> str:
    """Pull the assistant's text out of a Sarvam OpenAI-shape response and
    strip any <think>...</think> reasoning leakage (defensive — the chat
    handler in routers/sarvam.py already strips these, but this endpoint
    calls sarvam_client.chat directly so the strip happens here too)."""
    choices = (data.get("choices") or []) if isinstance(data, dict) else []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    raw = msg.get("content") or ""
    raw = re.sub(r"<think(?:ing)?>[\s\S]*?</think(?:ing)?>", "", raw)
    raw = re.sub(r"<think(?:ing)?>[\s\S]*", "", raw)
    return raw.strip()
