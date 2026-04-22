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

    url = f"{settings.SARVAM_BASE_URL}{_BATCH_STT_PATH}"
    headers = {"api-subscription-key": settings.SARVAM_API_KEY}

    # Sarvam accepts audio via multipart. Content type is best-effort —
    # the service infers from the bytes.
    files = {"file": (filename, audio_bytes, _content_type_for_filename(filename))}
    data = {"language_code": language_code, "model": model}

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, headers=headers, files=files, data=data)
    except httpx.TimeoutException as exc:
        logger.warning("Sarvam batch STT timeout (%.1fs): %s", timeout_seconds, exc)
        raise SttRetryable("timeout") from exc
    except httpx.RequestError as exc:
        logger.warning("Sarvam batch STT network error: %s", exc)
        raise SttRetryable("network") from exc

    if resp.status_code >= 500:
        logger.warning(
            "Sarvam batch STT 5xx (status=%d body=%s)",
            resp.status_code, resp.text[:300],
        )
        raise SttRetryable(f"status_{resp.status_code}")

    if resp.status_code >= 400:
        logger.error(
            "Sarvam batch STT 4xx (status=%d body=%s)",
            resp.status_code, resp.text[:300],
        )
        raise SttError(f"status_{resp.status_code}: {resp.text[:200]}")

    try:
        body = resp.json()
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
