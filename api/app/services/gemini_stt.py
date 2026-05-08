"""Gemini-backed batch speech-to-text — drop-in replacement for stt.py.

Mirrors ``services/stt.py``'s ``transcribe_audio`` signature exactly so
the dispatcher in ``stt.py`` can swap providers based on the
``STT_PROVIDER`` setting without callers changing.

Same exceptions:
  - ``SttRetryable``: transient (network / 5xx / timeout) — caller may
    retry, mark pending_retry, or fall back to Sarvam.
  - ``SttError``:     unrecoverable (4xx, malformed response, missing
    API key) — no point retrying with the same provider.

Cost is logged in ``sarvam_usage_log`` with ``service="gemini_stt"`` so
``/usage/cost`` reports treat it as a peer of ``service="stt"``
(Sarvam) — useful when comparing the two during the rollout window.

Why a separate module instead of folding into stt.py? Two reasons:
  1. Dual-log A/B mode (``STT_DUAL_LOG``) needs to call BOTH providers
     in parallel — keeping each provider in its own module makes the
     parallel call site readable.
  2. A future "fallback to Sarvam if Gemini fails" path needs both
     providers exposed; a dispatcher-only stt.py would have to import
     itself which is ugly.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from . import gemini_client, name_registry
from .stt import SttError, SttRetryable, _content_type_for_filename

logger = logging.getLogger(__name__)


_DEFAULT_MODEL = "gemini-2.5-flash"


async def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str = "audio.m4a",
    language_code: str = "od-IN",
    model: str = _DEFAULT_MODEL,
    timeout_seconds: float = 60.0,
) -> str:
    """Run Gemini audio-input STT. Returns the transcript.

    Same return / exception shape as ``stt.transcribe_audio`` so the
    dispatcher can swap providers without callers noticing.
    """
    if not audio_bytes:
        return ""

    mime_type = _content_type_for_filename(filename) or "application/octet-stream"

    try:
        transcript = await gemini_client.stt(
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            language_code=language_code,
            model=model,
            timeout=timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        logger.warning("Gemini STT timeout (%.1fs): %s", timeout_seconds, exc)
        raise SttRetryable("timeout") from exc
    except httpx.RequestError as exc:
        logger.warning("Gemini STT network error: %s", exc)
        raise SttRetryable("network") from exc
    except gemini_client.GeminiError as exc:
        sc = exc.status_code
        # Same retry rule as the Anthropic / Sarvam paths: 5xx / 429 /
        # 408 are worth retrying; 4xx-other are config / payload bugs.
        if sc and sc in (408, 429, 500, 502, 503, 504):
            logger.warning("Gemini STT %d, marking retryable", sc)
            raise SttRetryable(f"status_{sc}") from exc
        logger.error("Gemini STT failed (status=%s): %s", sc, exc)
        raise SttError(str(exc)) from exc

    # Apply the same Odia-name fixup the Sarvam path applies — Gemini
    # also occasionally emits Indian names in romanised English instead
    # of Odia script when the speaker code-switches mid-utterance.
    return name_registry.replace_english_names((transcript or "").strip())
