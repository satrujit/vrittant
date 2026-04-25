"""POST /api/llm/generate-story — server-owned story generation.

Why this is a dedicated endpoint
--------------------------------
Mobile shouldn't be picking the model. Mobile shouldn't be shipping a
copy of the system prompt either — that means a typo or improvement
needs an app store release. This endpoint owns:

  - the model (Claude Haiku 4.5; Sarvam-30b on fallback)
  - the system prompt
  - max_tokens, temperature, reasoning settings
  - post-processing (Odia digit normalization, purna virama spacing)

Mobile sends only what it has: the reporter's raw notes. The server
returns the polished article body and the name of the model that served
it (so we can see in logs/UI when the fallback fired).

Fallback chain
--------------
1. Try Anthropic Claude Haiku 4.5 (faithful to facts, obeys structure).
2. On TRANSIENT failure (timeout, 5xx, 429, 529, network error) →
   fall back to Sarvam-30b with the same system prompt. Logged with
   ``fallback_reason=...`` so the failure is grep-able.
3. On NON-TRANSIENT Anthropic failure (400/401/403): bubble up. Those
   are deploy/auth bugs and silent fallback would mask them forever.
4. On Sarvam failure after fallback: 502 to client.

We A/B'd Haiku vs Sarvam-30b on real Odia reporter notes (see
/tmp/haiku-ab/VERDICT.md, summarized in the commit message that
introduced this endpoint). Haiku won decisively on faithfulness,
structure, and latency; Sarvam stays as a safety net only.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel, Field

from ..deps import get_current_user
from ..models.user import User
from ..services import anthropic_client, sarvam_client
from ..services.anthropic_client import AnthropicError, is_transient_error

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# System prompt — single source of truth. Was previously a string constant
# in mobile/lib/features/create_news/providers/create_news_provider.dart;
# moved here so prompt tweaks ship as a backend deploy, not an APK release.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a senior Odia news editor. The reporter has dictated "
    "or typed raw notes for a news story. Your job is to weave "
    "these notes into a publishable Odia article body:\n"
    "1. Lead paragraph: who/what/when/where, in 1-2 sentences.\n"
    "2. Follow with supporting paragraphs in logical order.\n"
    "3. Use clean Odia, proper purna virama (।), and Odia numerals (୦-୯).\n"
    "4. PROPER NOUNS — copy CHARACTER-FOR-CHARACTER from the input. "
    "Names, places, organisations, designations: keep the exact "
    "spelling the reporter used, even if it looks unusual or you "
    "think it is a more common variant. Do NOT \"correct\" or "
    "normalise. If the same name appears with different spellings "
    "in the input, use the first occurrence consistently. Never "
    "invent names, places, dates, or quotes.\n"
    "5. SPEAKING FILLERS — strip dictation artifacts: hesitations "
    "(ahh, umm, ehi… ehi…), discourse markers (matlab, yaani, "
    "haan, to, achha, bujhilen, kahibaaku gale, thik achi), false "
    "starts, and word/phrase repetitions. Write like an editor, "
    "not a transcriber.\n"
    "6. Keep it tight — newspapers, not blog posts.\n"
    "Separate paragraphs with a blank line. Return ONLY the article "
    "body. No headline, no byline, no commentary."
)

# Model picks (centralized so a future swap is one constant change).
PRIMARY_MODEL = "claude-haiku-4-5"
FALLBACK_MODEL = "sarvam-30b"

# max_tokens budgets:
#   Haiku: 4096 is well over our observed P95 (562 tokens on 400-char input).
#   Sarvam: 8192 is the Pro tier cap on sarvam-30b; reasoning models burn
#   most of the budget in reasoning_content before emitting the article.
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
        "monitoring fallback rate. One of 'claude-haiku-4-5' (primary) "
        "or 'sarvam-30b' (fallback).",
    )
    fallback_used: bool = Field(
        default=False,
        description="True when Anthropic failed and Sarvam served. Surface "
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

    # ── Try Anthropic primary ────────────────────────────────────────────
    with attribution:
        try:
            anth_resp = await anthropic_client.chat(
                model=PRIMARY_MODEL,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": notes}],
                max_tokens=PRIMARY_MAX_TOKENS,
                temperature=0.3,
            )
            text = anthropic_client.extract_text(anth_resp)
            if not text:
                # Empty response is treated as a transient failure — fall
                # back to Sarvam rather than returning an empty body to the
                # user. Models occasionally emit only a refusal/empty turn.
                raise AnthropicError(
                    "anthropic returned empty content", status_code=None
                )
            return GenerateStoryResponse(
                body=_post_process(text),
                model=PRIMARY_MODEL,
                fallback_used=False,
            )
        except AnthropicError as exc:
            if not is_transient_error(exc):
                logger.error(
                    "generate_story: non-transient Anthropic failure "
                    "(status=%s, user=%s) — bubbling up: %s",
                    exc.status_code, user.id, exc,
                )
                raise HTTPException(
                    status_code=http_status.HTTP_502_BAD_GATEWAY,
                    detail=f"Anthropic error ({exc.status_code}): {exc}",
                )
            logger.warning(
                "generate_story: Anthropic transient failure "
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
