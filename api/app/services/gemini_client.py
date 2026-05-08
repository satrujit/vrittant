"""Gemini (Google AI Studio) chat + translate wrapper.

Same shape as ``anthropic_client.py``: thin httpx call with cost
logging into the shared ``sarvam_usage_log`` ledger so /usage/cost
reports group spend by story / user / bucket regardless of provider.

Calls hit Google AI Studio's ``generativelanguage.googleapis.com``
directly (not Vertex AI) — billed to whatever GCP project the API key
was created in (vrittant-f5ef2). Auth is API-key in the header; no
service-account token refresh dance needed.

Public API
----------
- ``chat(*, prompt, system=None, model=DEFAULT, max_tokens=2000, temperature=None)``
  Returns the assistant's text directly (no content-block unwrapping).
- ``chat_with_cached_system(*, prompt, system, cache_key, ttl_seconds=3600, ...)``
  Same as ``chat`` but pins ``system`` into an explicit Gemini cache
  the first time it sees ``cache_key``, then reuses the cache name on
  subsequent calls until TTL. Falls back to plain ``chat`` when the
  prompt is below the per-model minimum (Flash/Flash-Lite: 1024
  tokens). Use for any system prompt that's identical across calls AND
  large enough to qualify — see PROMPT CACHING NOTES below.
- ``translate(*, text, source_lang='auto', target_lang='en', ...)``
  Convenience wrapper for translate-style calls.

Cost is logged with ``service="gemini_chat"`` so it appears alongside
anthropic_chat / sarvam_chat rows in the same table.

PROMPT CACHING NOTES
--------------------
Gemini 2.5 supports two caching modes; we benefit from both:

1. **Implicit caching** (automatic, zero code) — Google silently
   caches stable prompt prefixes on its end and applies a 75% input-
   token discount when the same prefix shows up again within minutes.
   Reported in ``usageMetadata.cachedContentTokenCount``; we already
   pull that field and bill it at 25% in ``_cost_chat``. Nothing to
   wire — just keep prompts prefix-stable (system instruction
   identical across calls).

2. **Explicit caching** (``chat_with_cached_system`` here) — we
   create a ``cachedContents`` resource with the system prompt, get
   back a name like ``cachedContents/abc123``, and reference that
   instead of inlining the system text in subsequent calls. Same 75%
   discount, but unlike implicit caching the cache hit is guaranteed
   (no eviction roulette). Costs storage at the same input rate per
   hour the cache lives.

Threshold: explicit AND implicit caching require the cached portion
to be ≥1024 tokens (gemini-2.5-flash, gemini-2.5-flash-lite) or
≥4096 tokens (gemini-2.5-pro). Below that, the API rejects the
create-cache call AND implicit caching never engages.

Today the heaviest prompt in this codebase (the story-editor system
prompt in ``routers/generate_story.py``) is ~700–900 tokens — under
the threshold. ``chat_with_cached_system`` is wired up so caching
auto-engages the moment any prompt grows past 1024 tokens; in the
meantime it transparently falls through to plain ``chat`` and we
rely on implicit caching where Google decides to apply it.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from decimal import Decimal
from typing import Optional

import httpx

from ..config import settings
from .sarvam_client import _CURRENT, _write_log_row

logger = logging.getLogger(__name__)


# Pricing in USD per million tokens (Gemini 2.5 Flash-Lite, AI Studio
# tier as of 2026-04-29). Update when Google moves prices. INR conversion
# via the same constant the Anthropic client uses.
_USD_TO_INR = Decimal("84")
_PRICING = {
    "gemini-2.5-flash-lite": {
        "input_per_m": Decimal("0.10"),
        "output_per_m": Decimal("0.40"),
        # Audio-input is billed at a different SKU on the Studio tier —
        # 32 audio tokens per second of audio. Used by stt() / not by
        # plain chat(). Source: ai.google.dev/gemini-api/docs/pricing
        "audio_input_per_m": Decimal("0.30"),
    },
    "gemini-2.5-flash": {
        "input_per_m": Decimal("0.30"),
        "output_per_m": Decimal("2.50"),
        "audio_input_per_m": Decimal("1.00"),
    },
    "gemini-2.5-pro": {
        "input_per_m": Decimal("1.25"),
        "output_per_m": Decimal("10.00"),
        "audio_input_per_m": Decimal("3.00"),
    },
    # Gemini 3.x family. Pricing taken from the Standard-tier table
    # shown on ai.google.dev/gemini-api/docs/pricing (paid tier).
    # Update if Google revises rates — _cost_chat / _cost_stt log a
    # WARNING when no PRICING entry matches.
    "gemini-3.1-flash-lite": {
        "input_per_m": Decimal("0.25"),
        "output_per_m": Decimal("1.50"),
        "audio_input_per_m": Decimal("0.50"),
    },
    "gemini-3-flash": {
        "input_per_m": Decimal("0.25"),
        "output_per_m": Decimal("1.50"),
        "audio_input_per_m": Decimal("0.50"),
    },
}


class GeminiError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def is_transient_error(exc: BaseException) -> bool:
    """Same predicate shape as anthropic_client.is_transient_error so
    callers that already know how to retry around Anthropic can swap
    providers without changing their retry logic.

    Status codes treated as transient:
      - 408, 429, 500, 502, 503, 504 — standard server-side / rate-
        limit signals that callers should retry.
      - 599 — synthetic "client-observed empty content" signal raised
        by callers when Gemini returns a 200 OK with zero text in
        candidates. The empty-turn case happens on safety-filter
        refusals and on rare model hiccups; treating it as transient
        lets generate_story.py fall through to the Sarvam fallback
        instead of surfacing a 502 to the reporter.
    """
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, GeminiError) and exc.status_code is not None:
        return exc.status_code in (408, 429, 500, 502, 503, 504, 599)
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def chat(
    *,
    prompt: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: Optional[float] = None,
    timeout: float = 60.0,
    client: Optional[httpx.AsyncClient] = None,
) -> str:
    """POST to /v1beta/models/{model}:generateContent. Returns the text.

    The Studio API takes ``contents`` (list of role+parts) and an
    optional ``systemInstruction``. We serialize a single-turn user
    message + optional system block — fine for the chat / translate /
    classify / categorise use cases that we currently call.
    """
    if not _api_key():
        raise GeminiError("GEMINI_API_KEY is not configured", status_code=None)

    resolved_model = model or settings.GEMINI_DEFAULT_MODEL
    url = (
        f"{_base_url()}/v1beta/models/{resolved_model}:generateContent"
    )
    payload: dict = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]},
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    if temperature is not None:
        payload["generationConfig"]["temperature"] = temperature

    started = time.monotonic()
    status_code: Optional[int] = None

    try:
        async with _maybe_client(client, timeout) as c:
            resp = await c.post(url, json=payload, headers=_headers(), timeout=timeout)
            status_code = resp.status_code
            if resp.status_code >= 400:
                body_preview = resp.text[:500]
                _log_failed_call(
                    model=resolved_model,
                    started=started,
                    status_code=status_code,
                    error=f"http_{status_code}",
                )
                raise GeminiError(
                    f"gemini /generateContent {status_code}: {body_preview}",
                    status_code=status_code,
                )
            data = resp.json()
    except (httpx.RequestError, ValueError) as exc:
        _log_failed_call(
            model=resolved_model,
            started=started,
            status_code=status_code,
            error=type(exc).__name__,
        )
        raise GeminiError(f"gemini request failed: {exc}") from exc

    # Token usage. usageMetadata always present on a 200 — we just
    # log what's there and shrug if Google ever drops the field.
    usage = (data.get("usageMetadata") or {}) if isinstance(data, dict) else {}
    input_tokens = int(usage.get("promptTokenCount") or 0)
    output_tokens = int(usage.get("candidatesTokenCount") or 0)
    cached_tokens = int(usage.get("cachedContentTokenCount") or 0)

    cost = _cost_chat(resolved_model, input_tokens, cached_tokens, output_tokens)
    _write_log_row(
        service="gemini_chat",
        model=resolved_model,
        endpoint="/v1beta/generateContent",
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        cost_inr=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
    )
    return _extract_text(data)


async def chat_with_cached_system(
    *,
    prompt: str,
    system: str,
    cache_key: str,
    model: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: Optional[float] = None,
    ttl_seconds: int = 3600,
    timeout: float = 60.0,
    client: Optional[httpx.AsyncClient] = None,
) -> str:
    """Chat with the system prompt pinned to an explicit Gemini cache.

    First call for a given ``cache_key`` POSTs to
    ``/v1beta/cachedContents`` and remembers the returned cache name
    (e.g. ``cachedContents/abc123``) in process-local memory along with
    its expiry. Subsequent calls within TTL reference that cache name
    and only pay for the user prompt + output tokens; the system block
    bills at 25% of input rate.

    Falls back to plain :func:`chat` when:

    - the system prompt is below the per-model token minimum (Flash /
      Flash-Lite need ≥1024, Pro needs ≥4096) — Google rejects the
      create-cache call with HTTP 400; we cache that "uncacheable"
      verdict so we don't keep re-trying.
    - cache creation fails for any other reason — we don't want a
      cache-infrastructure bug to break the actual story-generation
      path. The fallback path still benefits from implicit caching.

    Concurrency: the in-memory registry is process-local. Each Cloud
    Run instance maintains its own cache references; that's fine —
    cache resources are cheap to create and TTL-expire on Google's
    side without us cleaning up.
    """
    resolved_model = model or settings.GEMINI_DEFAULT_MODEL
    cache_name = await _get_or_create_cache(
        cache_key=cache_key,
        model=resolved_model,
        system=system,
        ttl_seconds=ttl_seconds,
        timeout=timeout,
        client=client,
    )
    if cache_name is None:
        # Either the prompt is too small to cache, or the create call
        # failed — fall through to a normal chat call. Implicit
        # caching may still apply server-side.
        return await chat(
            prompt=prompt,
            system=system,
            model=resolved_model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            client=client,
        )

    # Cache hit path — reference the cache resource instead of inlining
    # systemInstruction. Google requires the model field to match the
    # one used at cache creation, which we enforce in _get_or_create_cache.
    if not _api_key():
        raise GeminiError("GEMINI_API_KEY is not configured", status_code=None)

    url = f"{_base_url()}/v1beta/models/{resolved_model}:generateContent"
    payload: dict = {
        "cachedContent": cache_name,
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]},
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
        },
    }
    if temperature is not None:
        payload["generationConfig"]["temperature"] = temperature

    started = time.monotonic()
    status_code: Optional[int] = None
    try:
        async with _maybe_client(client, timeout) as c:
            resp = await c.post(url, json=payload, headers=_headers(), timeout=timeout)
            status_code = resp.status_code
            if resp.status_code >= 400:
                body_preview = resp.text[:500]
                # If the cache reference is stale (e.g. evicted before
                # TTL on Google's side), invalidate our memo and retry
                # via the plain path so the user-facing request still
                # succeeds. Any other error: log + raise.
                if resp.status_code in (400, 404):
                    _CACHE_REGISTRY.pop(cache_key, None)
                    logger.warning(
                        "gemini cache reference rejected (%s) for key=%s — "
                        "falling back to inline system prompt: %s",
                        status_code, cache_key, body_preview,
                    )
                    return await chat(
                        prompt=prompt,
                        system=system,
                        model=resolved_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=timeout,
                        client=client,
                    )
                _log_failed_call(
                    model=resolved_model,
                    started=started,
                    status_code=status_code,
                    error=f"http_{status_code}",
                )
                raise GeminiError(
                    f"gemini /generateContent (cached) {status_code}: {body_preview}",
                    status_code=status_code,
                )
            data = resp.json()
    except (httpx.RequestError, ValueError) as exc:
        _log_failed_call(
            model=resolved_model,
            started=started,
            status_code=status_code,
            error=type(exc).__name__,
        )
        raise GeminiError(f"gemini cached request failed: {exc}") from exc

    usage = (data.get("usageMetadata") or {}) if isinstance(data, dict) else {}
    input_tokens = int(usage.get("promptTokenCount") or 0)
    output_tokens = int(usage.get("candidatesTokenCount") or 0)
    cached_tokens = int(usage.get("cachedContentTokenCount") or 0)
    cost = _cost_chat(resolved_model, input_tokens, cached_tokens, output_tokens)
    _write_log_row(
        service="gemini_chat",
        model=resolved_model,
        endpoint="/v1beta/generateContent[cached]",
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        cost_inr=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
    )
    return _extract_text(data)


# ---------------------------------------------------------------------------
# Speech-to-text via Gemini's audio-input mode
# ---------------------------------------------------------------------------
#
# Gemini 2.5 Flash and Flash-Lite accept audio as a `parts[].inlineData`
# blob (base64-encoded) alongside a text prompt. We use this as a cheaper
# alternative to Sarvam's /speech-to-text — see services/gemini_stt.py
# for the drop-in wrapper that mirrors services/stt.py's interface.
#
# Pricing comparison for a 30 s Odia voice note (≈960 audio tokens):
#   - Sarvam saaras:        ~₹0.25
#   - Gemini 2.5 Flash:     ~₹0.08   (3× cheaper)
#   - Gemini 2.5 Flash-Lite ~₹0.025  (10× cheaper, lower-quality audio)
#
# Quality on Odia is the open question — Sarvam is Indic-specialized.
# Recommended rollout: feature-flag both providers, dual-log for a few
# days to compare transcripts side-by-side, then commit.

# Default model for STT. 2.5 Flash-Lite is cheapest but its multilingual
# audio understanding is weaker than Flash on Indic languages — start
# on Flash and only flip to Flash-Lite after offline eval shows it's
# acceptable for Odia.
_STT_DEFAULT_MODEL = "gemini-2.5-flash"

# Mapping IETF / RFC 5646 codes used by the existing Sarvam path to
# language names Gemini will recognise in the prompt. Falls back to
# "the audio's original language" if a code we don't know shows up.
_LANG_NAMES = {
    "od-IN": "Odia (Oriya)",
    "or-IN": "Odia (Oriya)",
    "od":    "Odia (Oriya)",
    "or":    "Odia (Oriya)",
    "hi-IN": "Hindi",
    "hi":    "Hindi",
    "en-IN": "Indian English",
    "en-US": "English",
    "en":    "English",
    "bn-IN": "Bengali",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "mr-IN": "Marathi",
    "gu-IN": "Gujarati",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "pa-IN": "Punjabi",
}


def _build_stt_prompt(language_code: str) -> str:
    """Prompt that tells Gemini to act as a transcriber. Output ONLY
    the transcript — no preamble, no language label, no translation."""
    lang = _LANG_NAMES.get(language_code, "the audio's original language")
    return (
        f"You are a speech-to-text transcriber. Transcribe the following "
        f"audio in {lang}. Output ONLY the transcript text in the script "
        f"native to that language (Devanagari for Hindi, Odia script for "
        f"Odia, etc.). Do not translate. Do not add explanations, prefixes, "
        f"timestamps, speaker labels, or any commentary. If the audio "
        f"contains no speech, output an empty string."
    )


async def stt(
    *,
    audio_bytes: bytes,
    mime_type: str,
    language_code: str = "od-IN",
    model: Optional[str] = None,
    max_tokens: int = 2000,
    timeout: float = 60.0,
    client: Optional[httpx.AsyncClient] = None,
) -> str:
    """Transcribe ``audio_bytes`` via Gemini audio-in. Returns the transcript.

    ``mime_type`` should match the audio container (audio/mp4, audio/ogg,
    audio/mpeg, audio/wav, audio/aac, audio/webm, audio/flac). Gemini
    documents support for these; an unknown MIME results in a 400 from
    Gemini which we surface as a GeminiError so callers can decide
    whether to retry the Sarvam path or give up.

    Inline upload is capped by Google at ~20 MB request body. WhatsApp
    voice notes are typically <1 MB so this is fine; longer recordings
    from the live-dictation path may need the Files API which we don't
    plumb here yet — guard with a size check upstream if relevant.
    """
    if not audio_bytes:
        return ""
    if not _api_key():
        raise GeminiError("GEMINI_API_KEY is not configured", status_code=None)

    resolved_model = model or _STT_DEFAULT_MODEL
    url = f"{_base_url()}/v1beta/models/{resolved_model}:generateContent"

    payload: dict = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64.b64encode(audio_bytes).decode("ascii"),
                        }
                    },
                    {"text": _build_stt_prompt(language_code)},
                ],
            },
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            # Transcription is a deterministic-leaning task; lock
            # temperature low so the model doesn't paraphrase.
            "temperature": 0.0,
        },
    }

    started = time.monotonic()
    status_code: Optional[int] = None

    try:
        async with _maybe_client(client, timeout) as c:
            resp = await c.post(url, json=payload, headers=_headers(), timeout=timeout)
            status_code = resp.status_code
            if resp.status_code >= 400:
                body_preview = resp.text[:500]
                _log_failed_call(
                    model=resolved_model,
                    started=started,
                    status_code=status_code,
                    error=f"http_{status_code}",
                )
                raise GeminiError(
                    f"gemini stt {status_code}: {body_preview}",
                    status_code=status_code,
                )
            data = resp.json()
    except (httpx.RequestError, ValueError) as exc:
        _log_failed_call(
            model=resolved_model,
            started=started,
            status_code=status_code,
            error=type(exc).__name__,
        )
        raise GeminiError(f"gemini stt request failed: {exc}") from exc

    usage = (data.get("usageMetadata") or {}) if isinstance(data, dict) else {}
    input_tokens = int(usage.get("promptTokenCount") or 0)
    output_tokens = int(usage.get("candidatesTokenCount") or 0)

    cost = _cost_stt(resolved_model, input_tokens, output_tokens)
    _write_log_row(
        service="gemini_stt",
        model=resolved_model,
        endpoint="/v1beta/generateContent[audio]",
        input_tokens=input_tokens,
        cached_tokens=0,
        output_tokens=output_tokens,
        cost_inr=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
    )
    return _extract_text(data)


async def translate(
    *,
    text: str,
    source_lang: str = "auto",
    target_lang: str = "en",
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> str:
    """Translate ``text`` from ``source_lang`` to ``target_lang``.

    Same return-shape as a plain string. The legacy Sarvam translate
    callers stuff a payload dict and read ``data["translated_text"]``;
    we expose just the string and they unpack at the call site.
    """
    src = "auto-detect" if source_lang == "auto" else source_lang
    system = (
        "You are a faithful translator. Preserve all facts, names, "
        "places, numbers, and quotes exactly. Return ONLY the "
        "translation — no preamble, no commentary, no markdown fences."
    )
    user = (
        f"Translate the following from {src} to {target_lang}:\n\n{text}"
    )
    return await chat(
        prompt=user,
        system=system,
        model=model,
        max_tokens=2000,
        temperature=0.1,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _api_key() -> str:
    return settings.GEMINI_API_KEY or ""


def _base_url() -> str:
    return settings.GEMINI_BASE_URL.rstrip("/") or "https://generativelanguage.googleapis.com"


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": _api_key(),
    }


def _normalize_model(model: str) -> str:
    """Map preview / dated suffixes back to the base name we have prices
    for, so cost logging doesn't fall off if Google ships a -09-2025
    revision and we forget to update _PRICING."""
    base = model.split("/")[-1].split(":")[0]
    for canonical in _PRICING.keys():
        if base.startswith(canonical):
            return canonical
    return base


def _cost_chat(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> Decimal:
    p = _PRICING.get(_normalize_model(model))
    if not p:
        logger.warning("gemini_client: no PRICING for %r — cost will be 0", model)
        return Decimal("0")
    # Cached input tokens are billed at 25% of the regular input rate
    # on the Studio API tier; treat conservatively as 25% (rounds up
    # in our favor if Google later changes it).
    fresh_in = max(0, input_tokens - cached_tokens)
    cost_usd = (
        (Decimal(fresh_in) * p["input_per_m"] / Decimal(1_000_000))
        + (Decimal(cached_tokens) * p["input_per_m"] * Decimal("0.25") / Decimal(1_000_000))
        + (Decimal(output_tokens) * p["output_per_m"] / Decimal(1_000_000))
    )
    return (cost_usd * _USD_TO_INR).quantize(Decimal("0.0001"))


def _cost_stt(model: str, audio_input_tokens: int, output_tokens: int) -> Decimal:
    """Cost for an STT call. Input is billed at the audio rate, not the
    text-input rate — Google reports them in the same `promptTokenCount`
    field but the SKU is different. We bill the entire prompt at the
    audio rate; the small overhead of the system-instruction text in
    the prompt is rounded into it (a few hundred audio-equivalent
    tokens of slop is cheaper to ignore than to split apart).
    """
    p = _PRICING.get(_normalize_model(model))
    if not p:
        logger.warning("gemini_client: no PRICING for %r — stt cost will be 0", model)
        return Decimal("0")
    audio_rate = p.get("audio_input_per_m") or p["input_per_m"]
    cost_usd = (
        (Decimal(audio_input_tokens) * audio_rate / Decimal(1_000_000))
        + (Decimal(output_tokens) * p["output_per_m"] / Decimal(1_000_000))
    )
    return (cost_usd * _USD_TO_INR).quantize(Decimal("0.0001"))


def _extract_text(data: dict) -> str:
    """Pull the assistant's text out of a generateContent response.

    Gemini returns ``candidates[0].content.parts[*].text``. We only
    emit a single-turn response so candidate 0 is what we want.
    """
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    out: list[str] = []
    for p in parts:
        if isinstance(p, dict) and p.get("text"):
            out.append(p["text"])
    return "".join(out).strip()


# ---------------------------------------------------------------------------
# Explicit cache registry (process-local, in-memory)
# ---------------------------------------------------------------------------
#
# Maps a stable caller-chosen ``cache_key`` to either:
#
#   ("name", expires_at_monotonic)  — a live cache resource we can re-use
#   ("uncacheable", forever)        — Google rejected the create call;
#                                     don't bother re-trying this key
#
# We deliberately avoid a global lock around create-or-get: a concurrent
# duplicate-create just means two cache resources for the same content
# for ~1h, costing pennies. Simpler than a coroutine-aware lock.

import asyncio  # noqa: E402

_CACHE_REGISTRY: dict[str, tuple[str, float]] = {}
_UNCACHEABLE_SENTINEL = "__uncacheable__"
# Refresh a cache entry when fewer than this many seconds remain. Avoids
# a thundering-herd of stale-cache-rejected retries right at expiry.
_REFRESH_GUARD_SECONDS = 60


async def _get_or_create_cache(
    *,
    cache_key: str,
    model: str,
    system: str,
    ttl_seconds: int,
    timeout: float,
    client: Optional[httpx.AsyncClient],
) -> Optional[str]:
    """Return a Gemini cache resource name for ``cache_key`` or None.

    None means "fall back to inline system prompt" — either the prompt
    is too small to cache (sticky once we learn this for a given key)
    or a transient create error happened. Either way, callers should
    transparently use plain :func:`chat`.
    """
    now = asyncio.get_event_loop().time()
    cached = _CACHE_REGISTRY.get(cache_key)
    if cached is not None:
        name, expires_at = cached
        if name == _UNCACHEABLE_SENTINEL:
            return None
        if expires_at - now > _REFRESH_GUARD_SECONDS:
            return name
        # Stale or near-stale — fall through to recreate.

    if not _api_key():
        return None

    url = f"{_base_url()}/v1beta/cachedContents"
    payload: dict = {
        # Google requires the fully-qualified model path here, not the
        # bare model id — "models/gemini-2.5-flash" not "gemini-2.5-flash".
        "model": f"models/{model}",
        "systemInstruction": {"parts": [{"text": system}]},
        "ttl": f"{ttl_seconds}s",
    }
    try:
        async with _maybe_client(client, timeout) as c:
            resp = await c.post(url, json=payload, headers=_headers(), timeout=timeout)
            if resp.status_code == 400:
                # Most common 400 here is "minimum 1024 tokens"; mark
                # this key as uncacheable so we don't keep paying the
                # round-trip on every story.
                logger.info(
                    "gemini cache create rejected (400) for key=%s — "
                    "marking uncacheable: %s",
                    cache_key, resp.text[:300],
                )
                _CACHE_REGISTRY[cache_key] = (_UNCACHEABLE_SENTINEL, float("inf"))
                return None
            if resp.status_code >= 400:
                logger.warning(
                    "gemini cache create failed (%s) for key=%s — "
                    "falling back to inline this call: %s",
                    resp.status_code, cache_key, resp.text[:300],
                )
                return None
            data = resp.json()
    except httpx.RequestError as exc:
        logger.warning(
            "gemini cache create network error for key=%s: %s — falling back",
            cache_key, exc,
        )
        return None

    name = data.get("name") if isinstance(data, dict) else None
    if not name:
        logger.warning(
            "gemini cache create returned no name for key=%s — body=%s",
            cache_key, str(data)[:300],
        )
        return None

    # Use slightly less than TTL so we refresh just before expiry.
    expires_at = now + max(1, ttl_seconds - _REFRESH_GUARD_SECONDS)
    _CACHE_REGISTRY[cache_key] = (name, expires_at)
    logger.info(
        "gemini cache created: key=%s name=%s ttl=%ss",
        cache_key, name, ttl_seconds,
    )
    return name


def _log_failed_call(
    *,
    model: str,
    started: float,
    status_code: Optional[int],
    error: str,
) -> None:
    _write_log_row(
        service="gemini_chat",
        model=model,
        endpoint="/v1beta/generateContent",
        cost_inr=Decimal("0"),
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
        error=error[:200] if error else None,
    )


import contextlib  # noqa: E402


@contextlib.asynccontextmanager
async def _maybe_client(client: Optional[httpx.AsyncClient], timeout: float):
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient(timeout=timeout) as c:
        yield c
