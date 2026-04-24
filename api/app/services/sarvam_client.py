"""Single chokepoint for every Sarvam AI call we make.

Why this exists
---------------
Sarvam is called from ~10 places in this codebase. Without a wrapper we
have no way to answer "what did this story cost?" or "how much did the
news-fetcher LLM burn last month?". This module gives us:

  1. **One place** that talks to Sarvam (chat / translate / stt / tts).
  2. **Per-call cost calculation** using a static PRICING dict that
     mirrors Sarvam's published rates (https://www.sarvam.ai/pricing).
  3. **Attribution** via a contextvar — request handlers set
     ``cost_context(story_id=...)`` once at the top of the route and
     every nested Sarvam call inherits it. Background jobs use
     ``cost_context(bucket="news_fetcher")`` etc.
  4. **A DB row per call** in ``sarvam_usage_log`` so we can query
     spend after the fact.

Failure handling
----------------
Cost logging must NEVER break the calling request. If anything in the
ledger path fails (DB down, contextvar misconfigured, pricing missing),
we log a warning and let the original Sarvam response through unchanged.

Pricing source of truth
-----------------------
The PRICING dict below is hand-mirrored from Sarvam's pricing page. If
Sarvam changes rates, update PRICING — the next call will use the new
numbers. Reconcile against Sarvam's invoice monthly to catch drift.
"""
from __future__ import annotations

import contextlib
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing table (INR). Mirrors https://www.sarvam.ai/pricing as of 2026-04-24.
# ---------------------------------------------------------------------------
#
# Per-million-token rates for chat (input / cached input / output).
# Per-10K-character rates for translate and TTS.
# Per-hour rate for STT (we convert seconds → hours at compute time).
#
# Keys use lowercased, version-stripped model names so callers don't need
# to think about case or "v1" vs "v2.5". Lookups should normalize via
# ``_normalize_model`` below.

_CHAT_PRICING_PER_M_TOKENS: dict[str, dict[str, Decimal]] = {
    "sarvam-105b": {"input": Decimal("4"), "cached": Decimal("2.5"), "output": Decimal("16")},
    "sarvam-30b":  {"input": Decimal("2.5"), "cached": Decimal("1.5"), "output": Decimal("10")},
    # `sarvam-m` is the public alias for the 30b reasoning model — same price.
    "sarvam-m":    {"input": Decimal("2.5"), "cached": Decimal("1.5"), "output": Decimal("10")},
}

_TRANSLATE_PRICING_PER_10K_CHARS: dict[str, Decimal] = {
    "mayura": Decimal("20"),
    "translate-v1": Decimal("20"),  # newer Sarvam Translate V1 (same price)
}

_TTS_PRICING_PER_10K_CHARS: dict[str, Decimal] = {
    "bulbul": Decimal("30"),
}

_STT_PRICING_PER_HOUR: dict[str, Decimal] = {
    "saarika": Decimal("30"),
    "saaras":  Decimal("30"),
    # Diarized variants (Sarvam charges ₹45/hr if diarization is on).
    "saarika-diarized": Decimal("45"),
    "saaras-diarized":  Decimal("45"),
}

_VISION_PRICING_PER_PAGE: Decimal = Decimal("1.5")


def _normalize_model(model: str) -> str:
    """Strip version suffix and lowercase. ``saarika:v2.5`` -> ``saarika``."""
    if not model:
        return ""
    base = model.split(":", 1)[0].strip().lower()
    return base


# ---------------------------------------------------------------------------
# Attribution — contextvar set by request handlers / background jobs.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CostContext:
    story_id: Optional[str] = None
    bucket: Optional[str] = None
    user_id: Optional[str] = None


_CURRENT: ContextVar[CostContext] = ContextVar("sarvam_cost_context", default=CostContext())


@contextlib.contextmanager
def cost_context(
    *,
    story_id: Optional[str] = None,
    bucket: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """Set attribution for any Sarvam calls made inside this block.

    Nests cleanly — inner blocks override outer fields, others inherit.

        async with cost_context(story_id=story.id, user_id=user.id):
            await sarvam_client.translate(text)        # attributed to story
            await sarvam_client.chat(messages=[...])   # attributed to story
    """
    parent = _CURRENT.get()
    new = CostContext(
        story_id=story_id if story_id is not None else parent.story_id,
        bucket=bucket if bucket is not None else parent.bucket,
        user_id=user_id if user_id is not None else parent.user_id,
    )
    token = _CURRENT.set(new)
    try:
        yield new
    finally:
        _CURRENT.reset(token)


def current_cost_context() -> CostContext:
    """Read the attribution that would be applied to a Sarvam call right now."""
    return _CURRENT.get()


# ---------------------------------------------------------------------------
# Cost calculations
# ---------------------------------------------------------------------------

_PER_MILLION = Decimal("1000000")
_PER_10K = Decimal("10000")
_PER_HOUR = Decimal("3600")


def _cost_chat(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> Decimal:
    rates = _CHAT_PRICING_PER_M_TOKENS.get(_normalize_model(model))
    if not rates:
        logger.warning("sarvam_client: no PRICING for chat model=%r — cost will be 0", model)
        return Decimal("0")
    # Sarvam bills cached_tokens at the cached rate and the rest at the input rate.
    uncached = max(0, input_tokens - cached_tokens)
    return (
        Decimal(uncached) * rates["input"]
        + Decimal(cached_tokens) * rates["cached"]
        + Decimal(output_tokens) * rates["output"]
    ) / _PER_MILLION


def _cost_translate(model: str, characters: int) -> Decimal:
    rate = _TRANSLATE_PRICING_PER_10K_CHARS.get(_normalize_model(model))
    if not rate:
        logger.warning("sarvam_client: no PRICING for translate model=%r — cost will be 0", model)
        return Decimal("0")
    return (Decimal(characters) * rate) / _PER_10K


def _cost_tts(model: str, characters: int) -> Decimal:
    rate = _TTS_PRICING_PER_10K_CHARS.get(_normalize_model(model))
    if not rate:
        logger.warning("sarvam_client: no PRICING for tts model=%r — cost will be 0", model)
        return Decimal("0")
    return (Decimal(characters) * rate) / _PER_10K


def _cost_stt(model: str, audio_seconds: int, *, diarized: bool = False) -> Decimal:
    key = _normalize_model(model)
    if diarized:
        key = f"{key}-diarized"
    rate = _STT_PRICING_PER_HOUR.get(key)
    if not rate:
        logger.warning("sarvam_client: no PRICING for stt model=%r diarized=%s — cost will be 0", model, diarized)
        return Decimal("0")
    return (Decimal(audio_seconds) * rate) / _PER_HOUR


# ---------------------------------------------------------------------------
# DB write — single function, swallows all errors so logging never breaks
# the calling request.
# ---------------------------------------------------------------------------

def _write_log_row(**fields: Any) -> None:
    """Insert one row into sarvam_usage_log. Never raises."""
    # Lazy imports keep this module importable in environments where the
    # DB layer isn't configured (e.g. unit tests of pricing math).
    from sqlalchemy.exc import SQLAlchemyError

    from ..database import SessionLocal
    from ..models.sarvam_usage_log import SarvamUsageLog

    ctx = _CURRENT.get()
    fields.setdefault("story_id", ctx.story_id)
    fields.setdefault("bucket", ctx.bucket)
    fields.setdefault("user_id", ctx.user_id)

    db = None
    try:
        db = SessionLocal()
        db.add(SarvamUsageLog(**fields))
        db.commit()
    except SQLAlchemyError as exc:
        logger.warning("sarvam_client: failed to write usage log: %s", exc)
        if db is not None:
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("sarvam_client: unexpected error writing usage log: %s", exc)
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Public API — thin wrappers around httpx that also write a ledger row.
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://api.sarvam.ai"


def _base_url() -> str:
    return getattr(settings, "SARVAM_BASE_URL", None) or _DEFAULT_BASE_URL


def _api_key() -> str:
    return getattr(settings, "SARVAM_API_KEY", "") or ""


def _chat_headers() -> dict[str, str]:
    """Sarvam accepts both Bearer and api-subscription-key. We send both
    because different endpoints prefer different ones in practice."""
    key = _api_key()
    return {
        "Authorization": f"Bearer {key}",
        "api-subscription-key": key,
        "Content-Type": "application/json",
    }


async def chat(
    *,
    payload: dict,
    timeout: float = 30.0,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """POST to /v1/chat/completions and log cost.

    ``payload`` is the body as you'd send it directly (model, messages,
    temperature, max_tokens, etc.). Returns the parsed JSON response.

    Re-raises any httpx error after logging a row with the failure — this
    way failed calls still show up in the ledger (with cost=0) so we know
    when something's wrong upstream.
    """
    url = f"{_base_url()}/v1/chat/completions"
    headers = _chat_headers()
    model = payload.get("model", "")

    started = time.monotonic()
    status_code: Optional[int] = None
    error: Optional[str] = None
    data: dict = {}

    try:
        async with _maybe_client(client, timeout) as c:
            resp = await c.post(url, json=payload, headers=headers, timeout=timeout)
            status_code = resp.status_code
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        error = f"http_{exc.response.status_code}"
        _log_failed_call(service="chat", model=model, endpoint="/v1/chat/completions",
                         started=started, status_code=status_code, error=error)
        raise
    except (httpx.RequestError, ValueError) as exc:
        error = type(exc).__name__
        _log_failed_call(service="chat", model=model, endpoint="/v1/chat/completions",
                         started=started, status_code=status_code, error=error)
        raise

    usage = (data.get("usage") or {}) if isinstance(data, dict) else {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    cached_tokens = 0
    details = usage.get("prompt_tokens_details") or {}
    if isinstance(details, dict):
        # OpenAI/Sarvam shape: {"cached_tokens": N}
        cached_tokens = int(details.get("cached_tokens") or 0)

    cost = _cost_chat(model, input_tokens, cached_tokens, output_tokens)
    _write_log_row(
        service="chat",
        model=model,
        endpoint="/v1/chat/completions",
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        cost_inr=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
    )
    return data


async def translate(
    *,
    payload: dict,
    timeout: float = 30.0,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """POST to /translate (Mayura V1) and log cost.

    Cost is computed from ``len(payload['input'])`` because Sarvam's
    /translate response carries no usage data. Sarvam bills "rounded up
    to the nearest character per request" so input length matches the
    meter exactly.
    """
    url = f"{_base_url()}/translate"
    headers = _chat_headers()
    model = payload.get("model", "mayura:v1")
    input_text = payload.get("input") or ""
    char_count = len(input_text)

    started = time.monotonic()
    status_code: Optional[int] = None
    error: Optional[str] = None
    data: dict = {}

    try:
        async with _maybe_client(client, timeout) as c:
            resp = await c.post(url, json=payload, headers=headers, timeout=timeout)
            status_code = resp.status_code
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        error = f"http_{exc.response.status_code}"
        _log_failed_call(service="translate", model=model, endpoint="/translate",
                         started=started, status_code=status_code, error=error,
                         characters=char_count)
        raise
    except (httpx.RequestError, ValueError) as exc:
        error = type(exc).__name__
        _log_failed_call(service="translate", model=model, endpoint="/translate",
                         started=started, status_code=status_code, error=error,
                         characters=char_count)
        raise

    cost = _cost_translate(model, char_count)
    _write_log_row(
        service="translate",
        model=model,
        endpoint="/translate",
        characters=char_count,
        cost_inr=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
    )
    return data


async def stt(
    *,
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    model: str,
    language_code: str = "od-IN",
    diarized: bool = False,
    timeout: float = 60.0,
) -> dict:
    """POST to /speech-to-text and log cost.

    Cost is computed from the audio duration. We try the response's
    ``duration`` field first (Sarvam returns it for batch STT); if absent
    we fall back to estimating from byte size at 16kbps (this is a rough
    last-resort — log a warning so we know to fix it).
    """
    url = f"{_base_url()}/speech-to-text"
    headers = {"api-subscription-key": _api_key()}
    files = {"file": (filename, audio_bytes, content_type)}
    data_fields = {"language_code": language_code, "model": model}
    if diarized:
        data_fields["with_diarization"] = "true"

    started = time.monotonic()
    status_code: Optional[int] = None
    error: Optional[str] = None
    data: dict = {}

    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            resp = await c.post(url, headers=headers, files=files, data=data_fields)
            status_code = resp.status_code
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        error = f"http_{exc.response.status_code}"
        _log_failed_call(service="stt", model=model, endpoint="/speech-to-text",
                         started=started, status_code=status_code, error=error)
        raise
    except (httpx.RequestError, ValueError) as exc:
        error = type(exc).__name__
        _log_failed_call(service="stt", model=model, endpoint="/speech-to-text",
                         started=started, status_code=status_code, error=error)
        raise

    # Try response.duration (Sarvam sometimes returns this in seconds), else estimate.
    audio_seconds = 0
    duration_field = data.get("duration") if isinstance(data, dict) else None
    if isinstance(duration_field, (int, float)) and duration_field > 0:
        # Round UP — Sarvam bills to the nearest second per their pricing page.
        audio_seconds = int(duration_field) + (1 if (duration_field - int(duration_field)) > 0 else 0)
    else:
        # Last-resort estimate: ~16kbps for typical compressed speech.
        # Off by a factor of 2 either way — fine for "ballpark cost",
        # not fine for invoice reconciliation. Whoever wires the
        # callsite should pass duration explicitly when known.
        if audio_bytes:
            audio_seconds = max(1, len(audio_bytes) // 2000)
            logger.info(
                "sarvam_client.stt: response had no duration field; estimating "
                "%ds from %d bytes (rough). Consider passing duration explicitly.",
                audio_seconds, len(audio_bytes),
            )

    cost = _cost_stt(model, audio_seconds, diarized=diarized)
    _write_log_row(
        service="stt",
        model=model,
        endpoint="/speech-to-text",
        audio_seconds=audio_seconds,
        cost_inr=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
    )
    return data


def log_vision_cost(
    *,
    model: str = "document-intelligence",
    pages: int = 1,
    duration_ms: Optional[int] = None,
) -> None:
    """Manual cost log for Sarvam Document Intelligence (OCR).

    The SDK doesn't expose per-call hooks we can wrap, so the OCR routine
    calls this once per completed job with the page count.
    """
    cost = Decimal(pages) * _VISION_PRICING_PER_PAGE
    _write_log_row(
        service="vision",
        model=model,
        endpoint="document-intelligence",
        pages=pages,
        cost_inr=cost,
        duration_ms=duration_ms,
    )


def log_streaming_stt_cost(
    *,
    model: str,
    audio_seconds: int,
    diarized: bool = False,
    duration_ms: Optional[int] = None,
) -> None:
    """Manual cost log for the streaming STT WebSocket path.

    The WS proxy in routers/sarvam.py relays bytes directly to Sarvam, so
    this wrapper never sees the call. The proxy should call this once per
    session with the total audio seconds it relayed.
    """
    cost = _cost_stt(model, audio_seconds, diarized=diarized)
    _write_log_row(
        service="stt",
        model=model,
        endpoint="ws:/speech-to-text/streaming",
        audio_seconds=audio_seconds,
        cost_inr=cost,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _log_failed_call(
    *,
    service: str,
    model: str,
    endpoint: str,
    started: float,
    status_code: Optional[int],
    error: str,
    **extra: Any,
) -> None:
    """Write a row even when the call failed, with cost=0."""
    _write_log_row(
        service=service,
        model=model,
        endpoint=endpoint,
        cost_inr=Decimal("0"),
        duration_ms=int((time.monotonic() - started) * 1000),
        status_code=status_code,
        error=error[:200] if error else None,
        **extra,
    )


@contextlib.asynccontextmanager
async def _maybe_client(client: Optional[httpx.AsyncClient], timeout: float):
    """Use the caller's httpx client if provided, else open one for this call."""
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient(timeout=timeout) as c:
        yield c
