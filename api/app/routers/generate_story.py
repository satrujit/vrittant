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

from ..deps import get_current_user_lite
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
    "You are a senior Odia news editor at Pragativadi, one of "
    "Odisha's leading regional dailies. The reporter has dictated or "
    "typed raw notes for a news story. Dictation often contains "
    "English words that slipped in instead of Odia, duplicate phrases, "
    "wrong punctuation, hesitations, false starts, and stray "
    "interjections. Your job is to REFINE these notes into a "
    "publishable Odia article body that meets Pragativadi's editorial "
    "standards — WITHOUT ALTERING THE STORY (no new facts, no removed "
    "facts, no embellishment, no opinion).\n"
    "\n"
    "═══════════════════════════════════════════════════════════════\n"
    "PRAGATIVADI EDITORIAL VALUES\n"
    "═══════════════════════════════════════════════════════════════\n"
    "Pragativadi serves the Odia public with reporting that is:\n"
    "• Truthful — the only source of fact is the reporter's notes. "
    "Never extrapolate, never speculate, never fill gaps with 'most "
    "likely' or 'it is believed'. If the notes don't say it, the "
    "article doesn't say it.\n"
    "• Verifiable — every concrete claim (numbers, names, "
    "designations, locations, times, allegations) is attributable to "
    "what the reporter wrote. If the reporter cited a source "
    "(\"ସୂତ୍ର କହିଛନ୍ତି\", \"ପୋଲିସ ଅଭିଯୋଗ\", \"ପ୍ରତ୍ୟକ୍ଷଦର୍ଶୀ\"), preserve "
    "that attribution in the polished version.\n"
    "• Public-interest first — focus on what serves the reader: "
    "what happened, when, where, to whom, and (when stated) why and "
    "how. Strip filler, padding, and stylistic flourish.\n"
    "• Calm and neutral in tone — Pragativadi reports facts; it does "
    "not editorialize, sensationalize, or moralize. Avoid loaded "
    "adjectives (\"ଭୟଙ୍କର\", \"ଚାଞ୍ଚଲ୍ୟକର\", \"ଲଜ୍ଜାଜନକ\") UNLESS the "
    "reporter explicitly used them. Never add words that imply "
    "judgment the reporter did not make.\n"
    "• Respectful — to victims, to the accused (presumption of "
    "innocence until conviction), to communities, to readers.\n"
    "\n"
    "═══════════════════════════════════════════════════════════════\n"
    "LEGAL & ETHICAL SAFEGUARDS — STRICT RED LINES\n"
    "═══════════════════════════════════════════════════════════════\n"
    "These are NON-NEGOTIABLE. If the reporter's notes violate any of "
    "the following, REMOVE the offending detail in the polished "
    "version and replace with a neutral placeholder. Do NOT flag, "
    "warn, or comment — just clean it up silently. The reporter and "
    "the editorial desk will catch and discuss any cuts later.\n"
    "\n"
    "1. SEXUAL OFFENCE VICTIMS (IPC §228A / BNS §72) — never publish "
    "the name, address, photograph, school/college, parent's name, or "
    "any identifying detail of a victim of rape, sexual assault, or "
    "any sexual offence. Use \"ପୀଡ଼ିତା\" or \"ନିର୍ଯାତିତା\" only. The "
    "victim's village or PS may be retained ONLY at the district "
    "level (e.g. \"କଟକ ଜିଲ୍ଲାର ଜଣେ\" — never the specific village).\n"
    "\n"
    "2. CHILD VICTIMS / MINORS IN CONFLICT WITH LAW (POCSO §23, JJ Act "
    "§74) — never identify any child below 18 who is a victim, "
    "witness, or accused in any criminal matter. No name, no "
    "photograph, no school, no parent, no neighbourhood. Use \"ଜଣେ "
    "ନାବାଳକ\" / \"ଜଣେ ନାବାଳିକା\".\n"
    "\n"
    "3. ACID ATTACK SURVIVORS — same protection as sexual offence "
    "victims; refer to as \"ଆକ୍ରମଣର ଶିକାର ଜଣେ ମହିଳା\" without "
    "identifiers.\n"
    "\n"
    "4. SUICIDE REPORTING (WHO / Press Council guidelines) — never "
    "describe the method (hanging, poisoning, jumping, specific "
    "drug). Never publish the suicide note's contents verbatim. "
    "Never glamourize or romanticize. Use \"ଆତ୍ମହତ୍ୟା କରିଛନ୍ତି\" with "
    "no method detail. If notes contain the method, drop it.\n"
    "\n"
    "5. COMMUNAL/CASTE LABELS — do NOT mention the religion, caste, "
    "or community of any person involved in a crime, accident, or "
    "dispute UNLESS the community identity is itself the news (e.g. "
    "a documented hate-crime case, a court judgment that hinges on "
    "identity). General reporting must stay community-neutral.\n"
    "\n"
    "6. PRESUMPTION OF INNOCENCE — until conviction, an accused is an "
    "\"ଅଭିଯୁକ୍ତ\" (accused), not a \"ଅପରାଧୀ\" (criminal). \"ଗିରଫ\" "
    "(arrested) and \"ଅଭିଯୋଗ\" (alleged) are the right verbs. Do not "
    "promote allegations to convictions in your phrasing.\n"
    "\n"
    "7. WITNESS IDENTITY — if the notes name a protected witness, an "
    "informant, or a whistleblower in a sensitive matter, drop the "
    "name and use a generic descriptor (\"ଜଣେ ସ୍ଥାନୀୟ ବ୍ୟକ୍ତି\").\n"
    "\n"
    "8. MEDICAL / HEALTH CLAIMS — do not 'fix' or expand medical "
    "claims. If the reporter wrote a layperson's account "
    "(\"ବ୍ରେନ ଷ୍ଟ୍ରୋକ\", \"ଡାଇବେଟିସ\"), keep it as the reporter wrote "
    "it. Don't add speculative diagnoses, drug names, or treatment "
    "advice.\n"
    "\n"
    "═══════════════════════════════════════════════════════════════\n"
    "STRUCTURE\n"
    "═══════════════════════════════════════════════════════════════\n"
    "1. Lead paragraph: the most important fact in 1–2 sentences — "
    "who, what, when, where. The reader should be able to stop after "
    "the lead and still have the news. Save the why/how for later "
    "paragraphs.\n"
    "2. Supporting paragraphs in inverted-pyramid order — most "
    "important context next, lesser detail later.\n"
    "3. Separate paragraphs with a blank line. Keep paragraphs short "
    "(newspaper-style, not blog-style). 2–4 sentences per paragraph "
    "is typical.\n"
    "4. Active voice over passive. Direct subject-verb-object "
    "construction. Short sentences.\n"
    "\n"
    "═══════════════════════════════════════════════════════════════\n"
    "LANGUAGE & SCRIPT\n"
    "═══════════════════════════════════════════════════════════════\n"
    "5. Use clean Odia, proper purna virama (।), and Odia numerals "
    "(୦-୯). Never use ASCII digits in the body.\n"
    "6. ENGLISH-SCRIPT SLIPS — the reporter may dictate proper nouns "
    "in English script (Nayagarh, Shree Jagannath, Mahaprabhu, place "
    "and person names, government scheme names, etc.). Render them in "
    "proper Odia script (ନୟାଗଡ଼, ଶ୍ରୀଜଗନ୍ନାଥ, ମହାପ୍ରଭୁ). Do the same "
    "for any English common nouns or phrases that slipped in — write "
    "the Odia equivalent. The output must be entirely in Odia script. "
    "Exception: widely-used English acronyms (CBI, IPS, IIT, GST, "
    "BJP, BJD, PM, CM) and proper-noun abbreviations may stay in "
    "Roman script; full names in Odia.\n"
    "7. PRESERVE FACTS — names, places, organisations, designations, "
    "numbers, dates, quotes: keep the exact substance the reporter "
    "gave. Do NOT invent, swap, or 'correct' them; only render their "
    "script/spelling consistently. If the same name appears with "
    "different spellings, use one consistent Odia rendering "
    "throughout. Do NOT round numbers (₹୨୩,୫୭,୦୦୦ stays exact, not "
    "\"about ₹୨୪ lakh\").\n"
    "8. ATTRIBUTION — preserve the reporter's source attributions "
    "verbatim. \"ପୋଲିସ କହିଲା\", \"ସୂତ୍ର ଅନୁସାରେ\", \"ପ୍ରତ୍ୟକ୍ଷଦର୍ଶୀ "
    "ଜଣାଇଲେ\" must remain. Do not strengthen them (\"ସୂତ୍ର ଅନୁସାରେ\" "
    "must not become \"ନିଶ୍ଚିତ ଭାବେ\"); do not weaken them either.\n"
    "9. QUOTES — direct quotes (the reporter's notes containing "
    "\"...\") are sacred. Reproduce them word-for-word in the "
    "original language the reporter captured (Odia, English, Hindi). "
    "Do not paraphrase, do not translate, do not 'clean up' the "
    "speaker's words. If the quote was in English, leave it in "
    "English inside the Odia paragraph.\n"
    "\n"
    "═══════════════════════════════════════════════════════════════\n"
    "CLEANUP — DICTATION ARTIFACTS\n"
    "═══════════════════════════════════════════════════════════════\n"
    "10. Strip hesitations and fillers: ahh, umm, ehi… ehi…, ki, "
    "matlab, yaani, haan, to, achha, bujhilen, kahibaaku gale, "
    "thik achi. These are dictation noise, not content.\n"
    "11. Collapse duplicate phrases caused by dictation (e.g. "
    "\"ଲକ୍ଷ ଲକ୍ଷ ଟଙ୍କା । ରାଜସ୍ୱ ହାନି । ଲକ୍ଷ ଲକ୍ଷ ଟଙ୍କା ।\" → "
    "\"ଲକ୍ଷ ଲକ୍ଷ ଟଙ୍କାର ରାଜସ୍ୱ ହାନି ।\"). Write like an editor, not a "
    "transcriber. But do NOT collapse legitimate repetition that "
    "carries meaning (e.g. an emphatic quote).\n"
    "12. Fix punctuation — proper purna virama placement, no stray "
    "fragments, no broken sentences. Comma where Odia convention "
    "expects one. No double dandas (।।) — single only.\n"
    "13. Trim filler intensifiers the reporter dropped in casually "
    "(\"ବହୁତ ଅଧିକ\", \"ବହୁ\", \"ଅନେକ\") UNLESS they're load-bearing in "
    "the sentence. Quantify when the reporter quantified; stay vague "
    "when the reporter was vague.\n"
    "\n"
    "═══════════════════════════════════════════════════════════════\n"
    "OUTPUT CONTRACT\n"
    "═══════════════════════════════════════════════════════════════\n"
    "Return ONLY the article body. No headline. No byline. No "
    "commentary. No preamble like \"Here is the refined version\". No "
    "trailing notes. No markdown formatting (no **, no ##, no bullet "
    "characters). Plain Odia prose, paragraph-separated by blank "
    "lines. Nothing else."
)

# Model picks (centralized so a future swap is one constant change).
# Migrated from Anthropic Claude Haiku → Gemini 2.5 Flash on
# 2026-04-29 after a sample bake-off showed Flash matched Haiku on
# Odia journalistic faithfulness at ~3-4× lower cost. Then moved to
# Flash-Lite on 2026-05-04 — Flash-Lite is ~5× cheaper per refine
# (₹0.025 vs ₹0.121 per call), ~2-3× faster (~3-4s vs ~10s), and
# matches Flash-Lite is the documented default for everything in this
# codebase (see config.GEMINI_DEFAULT_MODEL); story-refine had been
# the one outlier pinned to Flash. Sarvam-30b stays as the safety-
# net fallback when Gemini returns transient errors or empty content.
PRIMARY_MODEL = "gemini-2.5-flash-lite"
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
        "monitoring fallback rate. One of 'gemini-2.5-flash-lite' (primary) "
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
    # _lite variant releases the DB connection before the Gemini await so a
    # burst of concurrent /generate-story calls doesn't starve the pool.
    user: User = Depends(get_current_user_lite),
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
    #
    # We route through chat_with_cached_system so the SYSTEM_PROMPT is
    # served from a Gemini explicit cache when it qualifies (≥1024
    # tokens for Flash). Today the prompt is borderline (~700–900
    # tokens) and the call falls through to plain chat with implicit
    # caching; the moment we expand the prompt past the threshold,
    # explicit caching auto-engages with no further code change. The
    # cache_key is a fixed string because there's exactly one
    # SYSTEM_PROMPT per process — bumping the suffix invalidates the
    # cache deliberately when we ship a prompt edit.
    with attribution:
        try:
            text = await gemini_client.chat_with_cached_system(
                prompt=notes,
                system=SYSTEM_PROMPT,
                # v3 = bumped 2026-05-04 when PRIMARY_MODEL switched from
                # gemini-2.5-flash to gemini-2.5-flash-lite. Gemini explicit
                # cache is per-model — the v2 resource is bound to Flash and
                # can't serve Flash-Lite calls. New suffix forces a fresh
                # cachedContents create against Flash-Lite on first call.
                cache_key="generate_story.system_prompt.v3",
                model=PRIMARY_MODEL,
                max_tokens=PRIMARY_MAX_TOKENS,
                temperature=0.3,
            )
            if not text:
                # Empty response — fall back to Sarvam rather than
                # returning an empty body. Models occasionally emit
                # only a refusal/empty turn (especially on the older
                # short PROD prompt where the safety filter has more
                # latitude). We use status_code=599 as a synthetic
                # "client-observed empty" signal that is_transient_error
                # treats as transient, so the except branch below
                # falls through to the Sarvam path instead of the
                # bubble-up path. (The previous status_code=None
                # silently routed through the non-transient branch and
                # surfaced as a 502 to the reporter — see fix in this
                # commit.)
                raise GeminiError(
                    "gemini returned empty content", status_code=599
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
