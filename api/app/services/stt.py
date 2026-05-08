"""Batch speech-to-text — provider-dispatching wrapper.

The streaming WS proxy in ``routers/sarvam.py`` is used for live dictation.
This module is the *non-streaming* path: hand it audio bytes, get a transcript
back. Used for:

  * Always-upload pipeline — every recording is sent here for transcription
    in the background, so we have the audio + transcript on file even when
    the live WS path returned nothing (network was bad, Sarvam was slow,
    user cancelled mid-stream, etc).
  * Manual retranscribe — reporter taps "Retranscribe" on a paragraph that
    came back wrong; we re-run STT against the saved audio.
  * Background retry sweep — paragraphs marked ``pending_retry`` are reprocessed.

Provider dispatch
-----------------
``settings.STT_PROVIDER`` selects the backend:
  - ``"sarvam"`` (default) — Sarvam batch /speech-to-text. Indic-specialized,
    ~₹30/hour at saaras tier.
  - ``"gemini"`` — Gemini 2.5 Flash audio-input mode. ~3× cheaper than Sarvam,
    weaker on Indic accents but rapidly improving. See services/gemini_stt.py.

When ``settings.STT_DUAL_LOG`` is True, every call hits BOTH providers in
parallel, returns the primary's transcript, and logs the secondary's
transcript / duration / cost in ``sarvam_usage_log`` for offline A/B
comparison. Doubles the spend per call — only enable during the eval
window.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from ..config import settings
from . import name_registry, sarvam_client

logger = logging.getLogger(__name__)
# Dedicated logger for STT A/B comparisons — operators can grep this
# in Cloud Logging to see primary vs shadow transcripts for the same
# audio without poking at the DB.
shadow_logger = logging.getLogger("stt.shadow")


# Sarvam batch STT endpoint. Same base URL as /translate and /v1/chat.
_BATCH_STT_PATH = "/speech-to-text"
_DEFAULT_MODEL = "saarika:v2.5"


class SttError(Exception):
    """Raised on unrecoverable STT failure (4xx, malformed response)."""


class SttRetryable(Exception):
    """Raised on transient failure — caller should mark pending_retry."""


async def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str = "audio.m4a",
    language_code: str = "od-IN",
    model: Optional[str] = None,
    timeout_seconds: float = 60.0,
) -> str:
    """Dispatcher. Routes to Sarvam or Gemini based on settings.STT_PROVIDER.

    The legacy ``model`` argument still applies to the Sarvam path
    (defaults to saarika:v2.5). The Gemini path uses
    ``settings.STT_GEMINI_MODEL``; pass ``model`` if you want to
    override per-call.

    When ``settings.STT_DUAL_LOG`` is True, runs both providers in
    parallel for offline comparison. Returns the primary; logs the
    secondary as a shadow row.
    """
    if not audio_bytes:
        return ""

    primary = (settings.STT_PROVIDER or "sarvam").lower()
    if primary not in ("sarvam", "gemini"):
        logger.warning(
            "Unknown STT_PROVIDER=%r, falling back to sarvam", settings.STT_PROVIDER,
        )
        primary = "sarvam"

    if not settings.STT_DUAL_LOG:
        return await _dispatch_one(
            primary,
            audio_bytes=audio_bytes,
            filename=filename,
            language_code=language_code,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    # Dual-log A/B mode: both providers in parallel, return primary,
    # log a comparison line. Each provider already writes its OWN
    # cost row to sarvam_usage_log via its client wrapper; we don't
    # duplicate that. The interesting artifact for operators is the
    # transcript text from each side — captured in a dedicated logger
    # ("stt.shadow") so it's grep-able in Cloud Logging without
    # touching the DB.
    secondary = "gemini" if primary == "sarvam" else "sarvam"
    primary_task = asyncio.create_task(_dispatch_one(
        primary, audio_bytes=audio_bytes, filename=filename,
        language_code=language_code, model=model,
        timeout_seconds=timeout_seconds,
    ))
    shadow_task = asyncio.create_task(_dispatch_one_safe(
        secondary, audio_bytes=audio_bytes, filename=filename,
        language_code=language_code, model=None,
        timeout_seconds=timeout_seconds,
    ))
    try:
        primary_result = await primary_task
    except Exception:
        # Shadow failure shouldn't mask a primary failure — but DO
        # await the shadow so it doesn't leak as a pending task.
        try:
            await shadow_task
        except Exception:  # pragma: no cover — already swallowed inside _dispatch_one_safe
            pass
        raise
    shadow_result = await shadow_task  # never raises (see _safe wrapper)
    _log_shadow_compare(
        primary=primary, primary_text=primary_result,
        shadow=secondary, shadow_text=shadow_result,
    )
    return primary_result


async def _dispatch_one(
    provider: str,
    *,
    audio_bytes: bytes,
    filename: str,
    language_code: str,
    model: Optional[str],
    timeout_seconds: float,
) -> str:
    """Single-provider call, raises ``SttError``/``SttRetryable`` like the
    original API."""
    if provider == "gemini":
        from . import gemini_stt
        gemini_model = model or settings.STT_GEMINI_MODEL
        return await gemini_stt.transcribe_audio(
            audio_bytes,
            filename=filename,
            language_code=language_code,
            model=gemini_model,
            timeout_seconds=timeout_seconds,
        )
    return await _sarvam_transcribe(
        audio_bytes,
        filename=filename,
        language_code=language_code,
        model=model or _DEFAULT_MODEL,
        timeout_seconds=timeout_seconds,
    )


async def _dispatch_one_safe(
    provider: str,
    *,
    audio_bytes: bytes,
    filename: str,
    language_code: str,
    model: Optional[str],
    timeout_seconds: float,
) -> Optional[str]:
    """Same as ``_dispatch_one`` but never raises — used for the shadow
    side of dual-log mode where a provider failure must not break the
    hot path. Returns the transcript on success, ``None`` on any
    failure (logged at INFO)."""
    try:
        return await _dispatch_one(
            provider,
            audio_bytes=audio_bytes,
            filename=filename,
            language_code=language_code,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        logger.info("STT shadow (%s) failed: %r", provider, exc)
        return None


def _log_shadow_compare(
    *,
    primary: str,
    primary_text: str,
    shadow: str,
    shadow_text: Optional[str],
) -> None:
    """Emit one structured INFO line per dual-log call. Operators grep
    'stt.shadow' in Cloud Logging to compare provider transcripts on
    the same audio. Truncated to 500 chars per side to keep log volume
    bounded; if you need full text raise the limit or write to GCS."""
    cap = 500
    p = (primary_text or "")[:cap]
    s = (shadow_text or "")[:cap] if shadow_text is not None else "<failed>"
    shadow_logger.info(
        "STT compare primary=%s shadow=%s | primary_text=%r | shadow_text=%r",
        primary, shadow, p, s,
    )


async def _sarvam_transcribe(
    audio_bytes: bytes,
    *,
    filename: str,
    language_code: str,
    model: str,
    timeout_seconds: float,
) -> str:
    """Sarvam-batch implementation of the transcribe_audio contract.

    Same exceptions and post-processing as the legacy single-provider
    code. Kept as a private helper so the dispatcher above can route
    to it (or to gemini_stt) based on STT_PROVIDER, and so the dual-log
    path can call both without cross-importing.
    """
    try:
        body = await sarvam_client.stt(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=_content_type_for_filename(filename) or "application/octet-stream",
            model=model,
            language_code=language_code,
            timeout=timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        logger.warning("Sarvam batch STT timeout (%.1fs): %s", timeout_seconds, exc)
        raise SttRetryable("timeout") from exc
    except httpx.RequestError as exc:
        logger.warning("Sarvam batch STT network error: %s", exc)
        raise SttRetryable("network") from exc
    except httpx.HTTPStatusError as exc:
        sc = exc.response.status_code
        if sc >= 500:
            logger.warning("Sarvam batch STT 5xx (status=%d body=%s)", sc, exc.response.text[:300])
            raise SttRetryable(f"status_{sc}") from exc
        logger.error("Sarvam batch STT 4xx (status=%d body=%s)", sc, exc.response.text[:300])
        raise SttError(f"status_{sc}: {exc.response.text[:200]}") from exc
    except ValueError as exc:
        raise SttError("malformed JSON response") from exc

    transcript = body.get("transcript")
    if transcript is None:
        # Some Sarvam responses use 'text' or nest under 'data'. Be lenient.
        transcript = body.get("text") or (body.get("data") or {}).get("transcript", "")
    # Sarvam often emits Odia place / personal names in romanised English; rewrite
    # them to Odia script using the in-memory registry (api/data/names.txt).
    return name_registry.replace_english_names((transcript or "").strip())


def _content_type_for_filename(filename: str) -> Optional[str]:
    name = (filename or "").lower()
    if name.endswith(".m4a"):
        return "audio/mp4"
    if name.endswith(".mp3"):
        return "audio/mpeg"
    if name.endswith(".wav"):
        return "audio/wav"
    if name.endswith(".aac"):
        return "audio/aac"
    if name.endswith(".ogg"):
        return "audio/ogg"
    if name.endswith(".webm"):
        return "audio/webm"
    if name.endswith(".flac"):
        return "audio/flac"
    return "application/octet-stream"
