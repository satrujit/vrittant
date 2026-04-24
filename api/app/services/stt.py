"""Sarvam batch speech-to-text helper.

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
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import settings
from . import sarvam_client

logger = logging.getLogger(__name__)


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
    model: str = _DEFAULT_MODEL,
    timeout_seconds: float = 60.0,
) -> str:
    """Run Sarvam batch STT against an audio buffer. Returns the transcript.

    Raises:
        SttRetryable: network error, 5xx, or timeout — caller should retry later.
        SttError:     4xx or malformed response — no point retrying.
    """
    if not audio_bytes:
        return ""

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
    return (transcript or "").strip()


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
