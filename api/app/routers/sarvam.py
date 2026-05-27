import array
import asyncio
import base64
import json
import logging
import os
import re
import ssl
import struct
import tempfile
import time
import zipfile
from typing import Optional

import certifi
import httpx
import websockets.exceptions
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File as FastAPIFile, WebSocket, WebSocketDisconnect, status as http_status
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..deps import get_current_org_id
from ..models.user import User
from ..services import transcription_quota
from ..models.story import Story
from ..services import stt as stt_service
from ..services.storage import save_file
from ..utils.tz import now_ist

# Use the legacy connect API (compatible with how Sarvam SDK connects)
try:
    from websockets.legacy.client import connect as ws_connect
except ImportError:
    from websockets import connect as ws_connect
import jwt
from jwt import PyJWTError as JWTError
from pydantic import BaseModel, Field

from ..config import settings
from ..deps import get_current_user, get_current_user_lite
from ..models.user import User
from ..services import gemini_client, name_registry, sarvam_client

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# WebSocket auth helper (can't use FastAPI Depends in WS handlers)
# ---------------------------------------------------------------------------

def _authenticate_ws(token: str) -> str:
    """Validate a JWT token and return the reporter_id (sub claim).

    Returns None if the token is invalid.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        reporter_id: str = payload.get("sub")
        if reporter_id is None:
            return None
        return reporter_id
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Task 2 – WebSocket STT proxy (transparent bidirectional relay)
# ---------------------------------------------------------------------------

# Sarvam emits text frames as JSON. Different message variants nest the
# transcript under different keys (top-level or inside ``data``); we rewrite
# any string we find at the known transcript fields. Unknown / unparseable
# messages pass through verbatim so we never break a future Sarvam protocol.
_TRANSCRIPT_FIELDS = ("transcript", "text")


def _rewrite_transcript_message(raw: str) -> str:
    """Run the name registry over any transcript fields inside a Sarvam frame.

    Returns the (possibly re-serialised) message. Falls back to the original
    string if the frame isn't JSON or doesn't carry a transcript field.
    """
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if not isinstance(payload, dict):
        return raw

    changed = False
    for field in _TRANSCRIPT_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and value:
            rewritten = name_registry.replace_english_names(value)
            if rewritten != value:
                payload[field] = rewritten
                changed = True
    nested = payload.get("data")
    if isinstance(nested, dict):
        for field in _TRANSCRIPT_FIELDS:
            value = nested.get(field)
            if isinstance(value, str) and value:
                rewritten = name_registry.replace_english_names(value)
                if rewritten != value:
                    nested[field] = rewritten
                    changed = True

    if not changed:
        return raw
    return json.dumps(payload, ensure_ascii=False)


# ── Gemini live-dictation handler ──────────────────────────────────
#
# Sliding-window pseudo-streaming via periodic batch transcription:
#
#   - Every WS frame from the mobile app carries raw PCM 16-bit mono @
#     16 kHz, either as raw bytes (Flutter) or wrapped in a JSON
#     envelope `{"audio": {"data": "<base64>", ...}}` (web reviewer
#     panel). We append the decoded PCM to a server-side buffer.
#   - Every ``_GEMINI_TICK_SECONDS`` we transcribe ONLY the NEW bytes
#     since the previous successful transcription (the "chunk"), and
#     append the result to a running cumulative transcript. The full
#     cumulative text is emitted to the client each tick as a partial.
#     This is the key difference from the original implementation,
#     which re-transcribed the entire growing buffer every tick —
#     that was 5–12× more expensive AND produced duplications because
#     each call's output drifted slightly from the prior call, which
#     fired the client's commit-on-divergence logic and double-wrote
#     content. With a sliding window each chunk is independent and
#     short (≈4 s), so the model stays anchored and outputs only the
#     new audio's transcript.
#   - When the client disconnects we transcribe whatever's left in
#     the buffer with ``is_final=True`` and emit a ``vad_end`` event
#     so the panel / app commits the last window.
#
# Trade-off: a word straddling a chunk boundary may be cut. With a
# 4 s tick this is rare; we mitigate by using a slightly looser tick
# (≥ ``_GEMINI_MIN_CHUNK_SECONDS`` of new audio required) so most
# chunks naturally end on a pause.
#
# Cost: a 30 s recording at 4 s ticks ≈ 7 chunks × ~130 audio tokens
# each = ~900 input tokens total. At gemini-2.5-flash-lite audio
# rates that's ~₹0.025 per 30 s session — comfortably below Sarvam
# streaming's ~₹0.25.

_GEMINI_TICK_SECONDS = 4.0
_GEMINI_RECEIVE_TIMEOUT = 1.0
# Don't fire a transcription unless we have at least this many seconds
# of NEW audio waiting — too-short chunks are noisy (Gemini sometimes
# returns empty for sub-second audio) and the inter-chunk boundary
# becomes more disruptive than the extra wait.
_GEMINI_MIN_CHUNK_SECONDS = 2.0
# 16 kHz × 16-bit × 1 ch = 32_000 bytes/sec.
_PCM_BYTES_PER_SEC = 32_000
# Cap a single chunk's audio at 60 s to keep each Gemini request well
# under the inline-data ceiling (~20 MB) and to keep model attention
# fresh. If the client somehow accumulates >60 s without us getting
# a chance to transcribe, we force a chunk-flush.
_GEMINI_MAX_CHUNK_BYTES = _PCM_BYTES_PER_SEC * 60
# Silence gate: RMS (root-mean-square energy) of each chunk is
# computed in pure Python; chunks below the configured threshold are
# dropped before reaching Gemini. RMS captures sustained energy across
# the whole chunk — it's far more robust than a peak-amplitude check,
# which a single transient spike (mic bump, distant noise) could fool
# into letting a silent chunk through. We tried peak-only first and
# it never fired in real reporter audio (silent_dropped=0 across all
# sessions on 2026-05-08) because phone mics with auto-gain produce
# enough ambient floor that peak>500 always.
#
# Threshold is read from settings.STT_SILENCE_RMS_THRESHOLD so we can
# tune in prod via env var without redeploying code.


def _chunk_peak_amplitude(pcm_bytes: bytes) -> int:
    """Maximum absolute sample value in a 16-bit signed PCM buffer.

    Kept around for diagnostic logging — RMS is the gating signal,
    but logging both peak and RMS during the eval helps us calibrate
    the threshold to real reporter audio.
    """
    if not pcm_bytes:
        return 0
    if len(pcm_bytes) % 2 != 0:
        pcm_bytes = pcm_bytes[: len(pcm_bytes) - (len(pcm_bytes) % 2)]
        if not pcm_bytes:
            return 0
    samples = array.array("h")
    samples.frombytes(pcm_bytes)
    if not samples:
        return 0
    hi = max(samples)
    lo = min(samples)
    return hi if hi >= -lo else -lo


def _chunk_rms(pcm_bytes: bytes) -> float:
    """Root-mean-square energy of a 16-bit signed PCM buffer.

    Pure Python computation — for a 4-second 16 kHz chunk (≈64 K
    samples) this takes ~30-50 ms. Adds <2% to per-chunk latency
    because Gemini's audio API call dominates at 2-4 s. We could
    accelerate with audioop-lts as a third-party dep but the
    overhead isn't worth a new dependency.
    """
    if not pcm_bytes:
        return 0.0
    if len(pcm_bytes) % 2 != 0:
        pcm_bytes = pcm_bytes[: len(pcm_bytes) - (len(pcm_bytes) % 2)]
        if not pcm_bytes:
            return 0.0
    samples = array.array("h")
    samples.frombytes(pcm_bytes)
    if not samples:
        return 0.0
    sum_sq = sum(s * s for s in samples)
    return (sum_sq / len(samples)) ** 0.5


def _is_chunk_silent(
    pcm_bytes: bytes,
    *,
    threshold: Optional[float] = None,
) -> bool:
    """True if the chunk's RMS energy is below the speech threshold.

    DEPRECATED for the streaming path — superseded by
    ``_compress_pcm_silence`` below, which performs sub-window analysis
    and is robust against the "1-2 s of speech inside a 4 s chunk"
    case that the whole-chunk RMS test misses (the chunk's average
    RMS gets pulled above threshold by the speech, leaving the silent
    portion to Gemini for hallucination). Kept for tests + diagnostic
    use.
    """
    if threshold is None:
        threshold = float(settings.STT_SILENCE_RMS_THRESHOLD)
    return _chunk_rms(pcm_bytes) < threshold


# Sub-window VAD constants.
# 200 ms windows: short enough that a single word's pause boundaries
# don't bleed across windows, long enough that RMS averages out
# instantaneous spikes.
_VAD_WINDOW_MS = 200
_VAD_PAD_WINDOWS = 1  # keep 1 window (200 ms) of context on each side of speech
# Minimum total speech in a chunk to bother calling Gemini. Below
# this threshold we treat the chunk as "essentially silent" and skip
# the API call. Bumped from 300 ms to 600 ms on 2026-05-09 after the
# Flash-Lite migration: ambient noise (fan, breath, distant voices)
# was passing the per-window RMS gate with ~300-500 ms of audio, and
# Flash-Lite was hallucinating "ଏହି ଘରଟି ବହୁତ ସୁନ୍ଦର" into the gap.
# 600 ms ≈ one Odia syllable + tail; below that, nothing useful
# transcribes anyway, so the false-negative cost is zero.
_VAD_MIN_SPEECH_BYTES = int(_PCM_BYTES_PER_SEC * 0.6)


# Known small-model hallucination phrases. Gemini-Flash-Lite has high-
# prior fallback sentences it emits when the input is too short or
# too ambient-noise-y to transcribe; they're constant across sessions
# and never appear in real reporter dictation. Strip them post-hoc so
# they don't bleed into the cumulative transcript. Append phrases as
# we observe them — a small, targeted denylist is preferred over
# trying to RMS-tune our way out of the problem (we'd reject quiet
# real speech alongside the noise).
_STT_HALLUCINATION_PHRASES = (
    "ଏହି ଘରଟି ବହୁତ ସୁନ୍ଦର",  # "this house is very beautiful" — Flash-Lite Odia (colloquial)
    "ଏହି ଘରଟି ବହୁତ ସୁନ୍ଦର।",
    "ଏହି ଗୃହଟି ବହୁତ ସୁନ୍ଦର",  # same phrase, formal register variant (ଗୃହ vs ଘର)
    "ଏହି ଗୃହଟି ବହୁତ ସୁନ୍ଦର।",
    "ମୁଁ ତୁମକୁ ଭଲପାଏ",  # "I love you" — observed 2026-05-09 on silence
    "ମୁଁ ତୁମକୁ ଭଲପାଏ।",
    "this house is very beautiful",
    "this house is so beautiful",
)


# Maximum output tokens for a single streaming chunk. A 4-5 s chunk
# of real Odia speech transcribes to roughly 50-80 tokens; 200 is
# plenty of headroom for slower / denser speech without leaving runway
# for the model's degenerate-repetition failure mode (observed
# 2026-05-09: a single chunk emitted "୩୦" 50+ times = ~1500 tokens).
# Acts as a structural ceiling — if the model hits the cap mid-runaway
# we still get a truncated, much-cheaper response, and the trigram-
# collapse below scrubs whatever did slip through.
_STT_STREAMING_MAX_TOKENS = 200

# When the configured STT model produces a transcript that fails
# quality checks (token-ratio anomaly, script drift, etc.) we retry
# the SAME chunk on this stronger model. Cost overhead is bounded by
# the quality-failure rate; in steady-state Flash-Lite handles >95%
# of chunks and the 5% retry budget keeps the bill well below all-
# Flash. If we're already configured to use Flash (or higher) the
# quality gate just drops bad chunks without retry.
_STT_FALLBACK_MODEL = "gemini-3.1-flash"

# Quality gate: max output tokens per second of audio. Real human
# speech tops out around 5-6 syllables/second; even with dense Indic
# token expansion that's roughly 10-15 tokens/sec at the high end. 30
# tokens/sec is ~3× faster than humanly possible — anything above is
# the model emitting filler / repetition rather than transcribing
# speech. Catches degenerate-repetition runaways even when the
# model output is structurally diverse (so the trigram collapse
# below misses it).
_MAX_OUTPUT_TOKENS_PER_SECOND = 30

# Quality gate: minimum fraction of alphabetic chars that must be in
# Odia script for an od-IN session. Below this we consider the
# transcript to have language-drifted (Tamil, Bengali, Devanagari,
# etc.) and retry on the fallback model. Set conservatively at 0.7
# so a transcript with embedded English names ("Mishra", "BJP", place
# names) still passes — typical Odia news copy is >95% Odia chars.
_MIN_ODIA_SCRIPT_RATIO = 0.7


def _odia_script_ratio(text: str) -> float:
    """Fraction of alphabetic characters in ``text`` that are Odia
    (U+0B00-U+0B7F). Numbers, digits, punctuation, whitespace are
    ignored. Returns 1.0 for transcripts with no alphabetic chars
    (numbers / punctuation only — neutral, not a drift signal).
    """
    odia = 0
    other_alpha = 0
    for ch in text:
        cp = ord(ch)
        if 0x0B00 <= cp <= 0x0B7F:
            odia += 1
        elif ch.isalpha():
            other_alpha += 1
    total = odia + other_alpha
    if total == 0:
        return 1.0
    return odia / total


def _check_chunk_quality(
    text: str,
    *,
    audio_seconds: float,
    output_tokens: int,
    expected_script_lang: str,
) -> Optional[str]:
    """Returns a short failure-reason string if ``text`` looks like a
    model failure (runaway repetition, language drift), else None.
    Empty transcripts pass — they're handled separately downstream.
    """
    if not text:
        return None
    # Token-ratio anomaly. Independent of the trigram collapse — catches
    # cases where the model's repetition is structurally diverse enough
    # to evade the collapse but quantitatively absurd.
    if audio_seconds > 0:
        ratio = output_tokens / audio_seconds
        if ratio > _MAX_OUTPUT_TOKENS_PER_SECOND:
            return f"token_ratio={ratio:.1f}/s"
    # Script-drift check. Only enforce when the session language is
    # Odia; if we add other Indic-language flavours later the same
    # gate can be templated per-language.
    if expected_script_lang.lower().startswith("od"):
        odia_ratio = _odia_script_ratio(text)
        if odia_ratio < _MIN_ODIA_SCRIPT_RATIO:
            return f"odia_ratio={odia_ratio:.2f}"
    return None


# Pattern that catches a token (any non-whitespace run) repeated 3+
# times consecutively — e.g. "୩୦ ୩୦ ୩୦ ୩୦ ୩୦". The capture group is
# the token and the back-reference matches subsequent identical
# occurrences separated by single whitespace runs. We collapse the
# match to a single occurrence; pairs ("ତିରିଶ ତିରିଶ") are left alone
# because Odia (and Indic languages generally) use word-doubling for
# emphasis, but no natural speech repeats the same token 3+ times.
_REPETITION_PATTERN = re.compile(r"(\S+)(?:\s+\1){2,}")


def _collapse_runaway_repetition(text: str) -> tuple[str, int]:
    """Collapse runs of 3+ identical consecutive tokens to a single
    occurrence. Returns (cleaned_text, num_runs_collapsed).
    """
    if not text:
        return text, 0
    runs_collapsed = 0
    def _sub(m):
        nonlocal runs_collapsed
        runs_collapsed += 1
        return m.group(1)
    cleaned = _REPETITION_PATTERN.sub(_sub, text)
    return cleaned, runs_collapsed


def _filter_hallucinations(text: str) -> tuple[str, bool]:
    """Return (cleaned_text, was_filtered).

    If the entire transcript matches a known hallucination phrase
    (modulo trailing punctuation / whitespace / case), returns ("", True).
    If the transcript merely contains the phrase as a prefix, strips it
    and returns the remainder. Otherwise returns the original text
    unchanged.
    """
    if not text:
        return text, False
    stripped = text.strip()
    bare = stripped.rstrip("।.,!? ").lower()
    for phrase in _STT_HALLUCINATION_PHRASES:
        p = phrase.rstrip("।.,!? ").lower()
        if bare == p:
            return "", True
        if bare.startswith(p):
            # Strip the phrase prefix and the punctuation that followed it.
            cut = stripped[len(phrase):].lstrip(" ।.,!?")
            return cut, True
    return text, False


def _compress_pcm_silence(
    pcm_bytes: bytes,
    *,
    sample_rate: int = 16000,
    window_ms: int = _VAD_WINDOW_MS,
    pad_windows: int = _VAD_PAD_WINDOWS,
    rms_threshold: Optional[float] = None,
) -> tuple[bytes, dict]:
    """Strip silent sub-windows from a PCM 16-bit chunk.

    Why per-window instead of whole-chunk: real dictation alternates
    speech and silence at sub-second timescales. A 4-s chunk
    containing "3 s silence + 1 s speech" has average RMS pulled
    above threshold by the speech burst, so the whole-chunk gate
    waves it through and Gemini transcribes 4 s of audio of which
    3 s is silence — exactly where small models hallucinate. Per-
    window analysis classifies each 200 ms slice independently and
    drops only the silent slices, sending Gemini just the speech
    portions.

    Each 200 ms window's RMS is computed independently. Windows
    above ``rms_threshold`` are kept; ``pad_windows`` of context are
    also retained on each side of every speech window so word
    boundaries (typically 50-150 ms of pause adjacent to a word)
    are preserved — concatenation feels natural to the model and
    we don't accidentally remove the breath before the next word.

    Returns ``(compressed_pcm, stats_dict)`` where ``stats_dict``
    contains:
      - ``original_ms``: input audio length
      - ``kept_ms``: output audio length (audio actually sent to Gemini)
      - ``windows_kept`` / ``windows_total``
    """
    if rms_threshold is None:
        rms_threshold = float(settings.STT_SILENCE_RMS_THRESHOLD)

    empty_stats = {
        "original_ms": 0, "kept_ms": 0,
        "windows_kept": 0, "windows_total": 0,
    }
    if not pcm_bytes:
        return b"", empty_stats

    # int16 PCM requires even-length payloads.
    if len(pcm_bytes) % 2 != 0:
        pcm_bytes = pcm_bytes[:-1]
    if not pcm_bytes:
        return b"", empty_stats

    samples_per_window = int(sample_rate * window_ms / 1000)
    bytes_per_window = samples_per_window * 2
    samples = array.array("h")
    samples.frombytes(pcm_bytes)

    n_windows = len(samples) // samples_per_window
    if n_windows == 0:
        # Sub-window-sized chunk — treat as one window. Decide by RMS.
        sum_sq = sum(s * s for s in samples)
        rms = (sum_sq / len(samples)) ** 0.5 if samples else 0.0
        original_ms = int(len(pcm_bytes) / 2 / sample_rate * 1000)
        if rms >= rms_threshold:
            return pcm_bytes, {
                "original_ms": original_ms, "kept_ms": original_ms,
                "windows_kept": 1, "windows_total": 1,
            }
        return b"", {
            "original_ms": original_ms, "kept_ms": 0,
            "windows_kept": 0, "windows_total": 1,
        }

    # Phase 1: classify each window as speech (True) or silence (False)
    # by its own RMS energy.
    is_speech = [False] * n_windows
    for w in range(n_windows):
        start = w * samples_per_window
        end = start + samples_per_window
        window = samples[start:end]
        sum_sq = sum(s * s for s in window)
        rms = (sum_sq / samples_per_window) ** 0.5
        is_speech[w] = rms >= rms_threshold

    # Phase 2: dilate speech regions by `pad_windows` on each side so
    # natural word-boundary pauses are preserved in the output.
    keep = [False] * n_windows
    for w in range(n_windows):
        if is_speech[w]:
            for d in range(-pad_windows, pad_windows + 1):
                idx = w + d
                if 0 <= idx < n_windows:
                    keep[idx] = True

    # Phase 3: emit kept windows (in order) into the output buffer.
    output = bytearray()
    for w in range(n_windows):
        if keep[w]:
            start = w * bytes_per_window
            output.extend(pcm_bytes[start:start + bytes_per_window])

    # Append any trailing partial-window bytes only if we kept the
    # last full window — otherwise the trailing fragment is part of
    # a silent stretch and should be dropped too.
    remainder_start = n_windows * bytes_per_window
    if remainder_start < len(pcm_bytes) and n_windows > 0 and keep[-1]:
        output.extend(pcm_bytes[remainder_start:])

    return bytes(output), {
        "original_ms": int(len(pcm_bytes) / 2 / sample_rate * 1000),
        "kept_ms": int(len(output) / 2 / sample_rate * 1000),
        "windows_kept": sum(keep),
        "windows_total": n_windows,
    }


def _wrap_pcm_as_wav(
    pcm: bytes,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    bits: int = 16,
) -> bytes:
    """Wrap raw PCM little-endian audio in a minimal 44-byte WAV
    container so Gemini's inline-data path recognises a valid file.

    Gemini accepts WAV/MP3/AAC/OGG/FLAC; we hand it WAV because that's
    a 0-cost transformation from the raw PCM the mobile app already
    sends.
    """
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm)
    fmt_chunk = struct.pack(
        "<4sIHHIIHH",
        b"fmt ", 16,
        1,                 # AudioFormat = 1 (PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
    )
    data_chunk = struct.pack("<4sI", b"data", data_size) + pcm
    riff = struct.pack(
        "<4sI4s",
        b"RIFF",
        4 + len(fmt_chunk) + len(data_chunk),
        b"WAVE",
    )
    return riff + fmt_chunk + data_chunk


async def _gemini_streaming_handler(
    ws: WebSocket,
    *,
    reporter_id: str,
    language_code: str,
) -> None:
    """Live-dictation path when STT_PROVIDER=gemini. See docstring above.

    Sliding-window state:
      - ``pending_chunk``: bytes of new audio not yet transcribed.
      - ``cumulative_text``: running transcript built by appending each
        chunk's transcription. This is what we ship to the client as
        the partial each tick.
    """
    pending_chunk = bytearray()
    cumulative_text = ""
    last_tick_at = time.monotonic()
    session_started = time.monotonic()
    # Per-session telemetry for debug
    chunk_count = 0
    silent_chunks_dropped = 0
    hallucinations_filtered = 0
    repetition_runs_collapsed = 0
    flash_fallbacks = 0
    total_audio_bytes = 0
    # Audio actually sent to Gemini after VAD compression. Diverges
    # from total_audio_bytes when chunks have silent stretches that
    # got stripped by _compress_pcm_silence — the gap is the cost
    # saving relative to a no-VAD pipeline.
    compressed_audio_bytes = 0
    # Mirror of every Gemini call's usage metadata. gemini_client.stt()
    # appends to this list so we can sum cost / tokens at session end
    # without DB round-trip. Each entry: {input_tokens, output_tokens,
    # cost_inr, duration_ms}.
    usage_sink: list[dict] = []

    async def emit_data(text: str, is_final: bool) -> None:
        try:
            await ws.send_text(json.dumps({
                "type": "data",
                "data": {"transcript": text, "is_final": is_final},
            }))
        except Exception:
            # Client gone — let the receive loop catch the disconnect.
            pass

    async def emit_event(event_name: str) -> None:
        try:
            await ws.send_text(json.dumps({
                "type": "events",
                "data": {"event": event_name},
            }))
        except Exception:
            pass

    async def flush_chunk(*, is_final: bool) -> None:
        """Transcribe ``pending_chunk`` (only the new audio), append to
        ``cumulative_text``, emit the cumulative transcript. Called
        whenever the tick interval has elapsed AND we have ≥
        ``_GEMINI_MIN_CHUNK_SECONDS`` of new audio waiting (or on
        ``is_final=True`` regardless of chunk size, so trailing audio
        at session end is captured).

        Passes the last few words of the cumulative transcript as
        ``prior_context`` so Gemini sees the conversational anchor —
        substantially reduces language-drift and silent-audio
        hallucinations on small models. See ``_build_stt_prompt`` in
        gemini_client for the prompt structure.
        """
        nonlocal cumulative_text, pending_chunk, chunk_count
        nonlocal silent_chunks_dropped, compressed_audio_bytes
        nonlocal hallucinations_filtered, repetition_runs_collapsed
        nonlocal flash_fallbacks

        if not pending_chunk:
            return

        chunk_bytes = bytes(pending_chunk)
        pending_chunk.clear()  # advance the window — these bytes are now committed
        chunk_count += 1

        # Sub-window VAD compression. Splits the chunk into 200 ms
        # windows, keeps only the ones above the speech RMS threshold
        # (with 200 ms padding around each speech window for natural
        # cadence), drops the rest. For a typical "1-2 s of speech in
        # a 4 s chunk" the compressed output is ~50% the size — sent
        # bytes drop by half AND the silent portions that would have
        # invited hallucinations are gone.
        compressed_bytes, _vad_stats = _compress_pcm_silence(chunk_bytes)

        # Whole-chunk silence: if the compressor returned <300 ms of
        # audio, the chunk was essentially silent. Skip the API call
        # entirely. On is_final we still emit the existing cumulative
        # so the client commits.
        if len(compressed_bytes) < _VAD_MIN_SPEECH_BYTES:
            silent_chunks_dropped += 1
            if is_final and cumulative_text:
                await emit_data(cumulative_text, is_final=True)
            return

        compressed_audio_bytes += len(compressed_bytes)

        # No text-based prior_context. The systemInstruction in
        # gemini_client.stt anchors language, the VAD's 200 ms padding
        # preserves word-boundary continuity, and dropping the text
        # anchor eliminates the echo-loop failure mode we hit on
        # small models (sliding-window + prior_context = the model
        # latches onto the text and re-emits it across chunks).

        wav = _wrap_pcm_as_wav(compressed_bytes)
        audio_seconds = len(compressed_bytes) / _PCM_BYTES_PER_SEC
        primary_model = settings.STT_GEMINI_MODEL
        try:
            text = await gemini_client.stt(
                audio_bytes=wav,
                mime_type="audio/wav",
                language_code=language_code,
                model=primary_model,
                max_tokens=_STT_STREAMING_MAX_TOKENS,
                usage_sink=usage_sink,
            )
        except Exception as exc:
            logger.warning(
                "Gemini stream STT failed (reporter=%s, chunk=%d, bytes=%d): %r",
                reporter_id, chunk_count, len(chunk_bytes), exc,
            )
            return

        # Quality gate (token-ratio anomaly + script-drift). Run on the
        # raw primary output BEFORE name-replacement / collapse / phrase
        # filter, so the gate sees what Gemini actually produced. If the
        # primary model failed AND it isn't already the fallback, retry
        # the same chunk on the stronger Flash model. This is the
        # reactive routing strategy: cheap default, escalate only on
        # detected failure. ~5% expected fallback rate based on Flash-
        # Lite quality observed so far; cost overhead bounded by that.
        primary_usage = usage_sink[-1] if usage_sink else {}
        primary_output_tokens = int(primary_usage.get("output_tokens") or 0)
        primary_failure = _check_chunk_quality(
            text or "",
            audio_seconds=audio_seconds,
            output_tokens=primary_output_tokens,
            expected_script_lang=language_code,
        )
        if primary_failure and primary_model != _STT_FALLBACK_MODEL:
            logger.info(
                "Gemini STT: chunk %d quality fail on %s (%s) — "
                "retrying on %s (reporter=%s)",
                chunk_count, primary_model, primary_failure,
                _STT_FALLBACK_MODEL, reporter_id,
            )
            try:
                fallback_text = await gemini_client.stt(
                    audio_bytes=wav,
                    mime_type="audio/wav",
                    language_code=language_code,
                    model=_STT_FALLBACK_MODEL,
                    max_tokens=_STT_STREAMING_MAX_TOKENS,
                    usage_sink=usage_sink,
                )
                flash_fallbacks += 1
                # Re-check the fallback's output. If even Flash fails the
                # gate (rare but possible — genuinely bad audio), drop the
                # chunk entirely rather than emit either bad transcript.
                fb_usage = usage_sink[-1] if usage_sink else {}
                fb_output_tokens = int(fb_usage.get("output_tokens") or 0)
                fb_failure = _check_chunk_quality(
                    fallback_text or "",
                    audio_seconds=audio_seconds,
                    output_tokens=fb_output_tokens,
                    expected_script_lang=language_code,
                )
                if fb_failure:
                    logger.info(
                        "Gemini STT: fallback also failed quality (%s) — "
                        "dropping chunk %d", fb_failure, chunk_count,
                    )
                    text = ""
                else:
                    text = fallback_text
            except Exception as exc:
                logger.warning(
                    "Gemini STT fallback to %s failed (chunk=%d): %r — "
                    "dropping chunk", _STT_FALLBACK_MODEL, chunk_count, exc,
                )
                text = ""

        text = name_registry.replace_english_names((text or "").strip())

        # Collapse runaway repetition before any other filtering so the
        # hallucination matcher sees normalised text. Flash-Lite has a
        # degenerate-repetition failure mode where a token (typically a
        # number like "୩୦") gets emitted dozens of times in a row;
        # observed 2026-05-09 with output_tokens=2029 on an 18 s session.
        # The 200-token output cap above prevents catastrophic cost; this
        # collapse cleans the truncated runaway out of the transcript.
        text, runs_collapsed = _collapse_runaway_repetition(text)
        if runs_collapsed:
            repetition_runs_collapsed += 1
            logger.info(
                "Gemini STT: collapsed %d runaway repetition run(s) "
                "(reporter=%s, chunk=%d, model=%s)",
                runs_collapsed, reporter_id, chunk_count, settings.STT_GEMINI_MODEL,
            )

        # Strip known small-model hallucinations (e.g. "ଏହି ଘରଟି ବହୁତ ସୁନ୍ଦର"
        # — Flash-Lite's high-prior fallback on near-silent / ambient-
        # noise audio). The VAD gate catches most of it; this is the
        # belt-and-braces line of defence for what slips through.
        text, was_hallucinated = _filter_hallucinations(text)
        if was_hallucinated:
            hallucinations_filtered += 1
            logger.info(
                "Gemini STT: filtered hallucination "
                "(reporter=%s, chunk=%d, model=%s)",
                reporter_id, chunk_count, settings.STT_GEMINI_MODEL,
            )

        if not text:
            # Empty transcript for this chunk (silence / model returned
            # nothing / hallucination filtered). Don't append; if final,
            # still emit the existing cumulative so the client commits.
            if is_final and cumulative_text:
                await emit_data(cumulative_text, is_final=True)
            return

        cumulative_text = (
            (cumulative_text + " " + text).strip()
            if cumulative_text
            else text
        )
        await emit_data(cumulative_text, is_final=is_final)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(
                    ws.receive(), timeout=_GEMINI_RECEIVE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                # No frame in the receive window — check the tick.
                now = time.monotonic()
                ready = len(pending_chunk) >= int(
                    _PCM_BYTES_PER_SEC * _GEMINI_MIN_CHUNK_SECONDS
                )
                tick_elapsed = (now - last_tick_at) >= _GEMINI_TICK_SECONDS
                if ready and tick_elapsed:
                    await flush_chunk(is_final=False)
                    last_tick_at = now
                continue

            if msg["type"] == "websocket.disconnect":
                break

            if msg["type"] != "websocket.receive":
                continue

            payload = msg.get("text") or msg.get("bytes")
            if not payload:
                continue

            if isinstance(payload, str):
                # JSON envelope: {"audio": {"data": "<b64 pcm>", ...}}
                try:
                    env = json.loads(payload)
                except (ValueError, TypeError):
                    continue
                audio_obj = env.get("audio") or {}
                b64 = audio_obj.get("data")
                if not b64:
                    continue
                try:
                    decoded = base64.b64decode(b64)
                except Exception:
                    continue
                pending_chunk.extend(decoded)
                total_audio_bytes += len(decoded)
            elif isinstance(payload, (bytes, bytearray)):
                pending_chunk.extend(payload)
                total_audio_bytes += len(payload)

            # Hard cap: if a chunk somehow grows past _GEMINI_MAX_CHUNK_BYTES
            # (60 s of audio without a tick firing — shouldn't happen
            # with the timeout-based loop, but guard regardless), force
            # a flush.
            if len(pending_chunk) >= _GEMINI_MAX_CHUNK_BYTES:
                await flush_chunk(is_final=False)
                last_tick_at = time.monotonic()
                continue

            now = time.monotonic()
            ready = len(pending_chunk) >= int(
                _PCM_BYTES_PER_SEC * _GEMINI_MIN_CHUNK_SECONDS
            )
            if ready and (now - last_tick_at) >= _GEMINI_TICK_SECONDS:
                await flush_chunk(is_final=False)
                last_tick_at = now

        # Client disconnected — flush any trailing audio (regardless
        # of length — we want to capture the last 0.5 s if that's all
        # they said) and commit.
        await flush_chunk(is_final=True)
        if cumulative_text:
            await emit_event("vad_end")

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error(
            "Gemini stream STT fatal (reporter=%s): %r",
            reporter_id, exc,
        )
    finally:
        duration = time.monotonic() - session_started
        gemini_calls = len(usage_sink)
        total_cost = sum(float(u.get("cost_inr") or 0) for u in usage_sink)
        total_input = sum(int(u.get("input_tokens") or 0) for u in usage_sink)
        total_output = sum(int(u.get("output_tokens") or 0) for u in usage_sink)
        # Audio retained ratio: how much of the recorded audio actually
        # made it to Gemini after sub-window VAD. 100% = no compression
        # (every window was speech). Lower is better — silent stretches
        # are being correctly stripped.
        audio_retained_pct = (
            compressed_audio_bytes / total_audio_bytes * 100
            if total_audio_bytes > 0 else 0.0
        )
        logger.info(
            "Gemini STT session ended (reporter=%s, duration=%.1fs, "
            "audio_bytes=%d, audio_to_gemini=%d (%.1f%%), "
            "chunks=%d, silent_dropped=%d, hallucinations_filtered=%d, "
            "repetitions_collapsed=%d, flash_fallbacks=%d, "
            "gemini_calls=%d, cost=₹%.4f, input_tokens=%d, output_tokens=%d)",
            reporter_id, duration, total_audio_bytes,
            compressed_audio_bytes, audio_retained_pct,
            chunk_count, silent_chunks_dropped, hallucinations_filtered,
            repetition_runs_collapsed, flash_fallbacks,
            gemini_calls, total_cost, total_input, total_output,
        )

        # ── Record monthly transcription usage ────────────────────────
        # Counted in mic-on seconds (total_audio_bytes / pcm_rate),
        # NOT in audio-sent-to-Gemini seconds. Reporters perceive
        # their dictation by wall-clock; if we counted only post-VAD
        # audio the on-screen "X minutes left" badge would diverge
        # from their lived experience. Failure is swallowed inside
        # add_usage — quota tracking must never block session close.
        used_seconds = int(round(total_audio_bytes / _PCM_BYTES_PER_SEC))
        if used_seconds > 0:
            usage_db = SessionLocal()
            try:
                transcription_quota.add_usage(
                    usage_db, user_id=reporter_id, seconds=used_seconds,
                )
            finally:
                usage_db.close()

        try:
            await ws.close()
        except Exception:
            pass


@router.websocket("/ws/stt")
async def websocket_stt_proxy(
    ws: WebSocket,
    token: str,
    language_code: str = "od-IN",
    model: str = "saaras:v3",
):
    """Bidirectional relay between the Flutter client and Sarvam's streaming
    STT WebSocket.

    Maintains a single persistent upstream connection. If Sarvam disconnects
    (e.g. due to idle timeout), the proxy automatically reconnects and
    replays any queued audio — no gaps, no lost words.
    """

    # 1. Authenticate
    reporter_id = _authenticate_ws(token)
    if reporter_id is None:
        await ws.close(code=4001, reason="Invalid or missing token")
        return

    await ws.accept()
    logger.info(f"STT proxy: connected (reporter={reporter_id})")

    # ── Per-reporter monthly STT quota gate ───────────────────────────
    # Refuse the session up-front if the reporter has exhausted their
    # monthly transcription budget (default 3h, configurable via
    # users.monthly_transcription_limit). The mobile client also caches
    # this state and disables the mic button locally — this server-
    # side check is the source of truth and cannot be bypassed by a
    # stale or tampered client.
    quota_db = SessionLocal()
    try:
        reporter = quota_db.query(User).filter(User.id == reporter_id).one_or_none()
        if reporter is not None and transcription_quota.is_over_quota(quota_db, reporter):
            status = transcription_quota.get_status(quota_db, reporter)
            logger.info(
                "STT proxy: quota exhausted (reporter=%s, used=%ds, limit=%ds)",
                reporter_id, status["used_seconds"], status["limit_seconds"],
            )
            try:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "data": {
                        "code": "monthly_quota_exhausted",
                        "limit_seconds": status["limit_seconds"],
                        "used_seconds": status["used_seconds"],
                    },
                }))
            except Exception:
                pass
            await ws.close(code=4002, reason="Monthly transcription quota exhausted")
            return
    finally:
        quota_db.close()

    # ── Provider dispatch ─────────────────────────────────────────────
    # When STT_PROVIDER=gemini, route the live-dictation stream through
    # the Gemini batch API in chunks (pseudo-streaming). Mobile app
    # sees the same `{type: "data", data: {transcript, is_final}}`
    # message shape, so no client change is required. UX trade-off:
    # partials arrive every ~4s instead of Sarvam streaming's ~200ms.
    if (settings.STT_PROVIDER or "sarvam").lower() == "gemini":
        logger.info(
            "STT proxy: routing to Gemini (reporter=%s, model=%s)",
            reporter_id, settings.STT_GEMINI_MODEL,
        )
        await _gemini_streaming_handler(
            ws,
            reporter_id=reporter_id,
            language_code=language_code,
        )
        return

    # 2. Sarvam connection details
    sarvam_url = (
        f"wss://api.sarvam.ai/speech-to-text/ws"
        f"?language-code={language_code}&model={model}"
    )
    sarvam_headers = {"api-subscription-key": settings.SARVAM_API_KEY}
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    # Per-user local state
    sarvam_ws = None
    client_alive = True
    audio_queue = asyncio.Queue()
    # Track total audio bytes relayed so we can log a single STT cost row
    # when the session ends. Streaming STT uses raw PCM 16-bit mono @ 16kHz
    # by default = 32000 bytes/second; if Sarvam ever changes this we'll
    # under/over-bill ourselves until the rate is updated.
    total_audio_bytes = 0
    session_started = time.monotonic()

    # --- Task 1: Read from Flutter client, enqueue audio chunks -----------
    async def read_client():
        nonlocal client_alive, total_audio_bytes
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.receive":
                    payload = msg.get("text") or msg.get("bytes")
                    if payload:
                        if isinstance(payload, (bytes, bytearray)):
                            total_audio_bytes += len(payload)
                        await audio_queue.put(payload)
                elif msg["type"] == "websocket.disconnect":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            client_alive = False
            await audio_queue.put(None)
            # CRITICAL: also force-close the upstream Sarvam WS so the main
            # loop's `await relay_task` returns. Without this, the relay
            # task stays parked inside `async for message in s_ws` until
            # Sarvam decides to close on its own — which empirically can
            # be hours. While wedged, the proxy holds a Cloud Run instance
            # from scaling down AND a fresh recording from the same reporter
            # opens a SECOND parallel server-side session because the old
            # one is still alive. Closing the Sarvam ref here cascades:
            # ConnectionClosed on the relay → relay_task completes → main
            # loop checks client_alive=False → breaks → cleanup runs.
            s_ws = sarvam_ws
            if s_ws is not None:
                try:
                    await s_ws.close()
                except Exception:
                    pass

    # --- Task 2: Dequeue audio and send to Sarvam WS ---------------------
    async def send_to_sarvam():
        while client_alive:
            chunk = await audio_queue.get()
            if chunk is None:
                break
            # If Sarvam isn't connected yet (initial connect still in
            # flight, or reconnect after a drop), DO NOT drop the chunk
            # — re-queue it so it's there when sarvam_ws comes back.
            # The previous `if sarvam_ws is not None: send` swallowed
            # those chunks silently; reporters who started speaking
            # before the upstream WS finished opening lost the first
            # 100–500ms of dictation. Worse, if Sarvam is mid-reconnect
            # for 1–2s, several seconds of audio went into the void.
            if sarvam_ws is None:
                await audio_queue.put(chunk)
                await asyncio.sleep(0.05)
                continue
            try:
                await sarvam_ws.send(chunk)
            except websockets.exceptions.ConnectionClosed:
                # Same re-queue path — reconnect loop will replay it.
                await audio_queue.put(chunk)
                await asyncio.sleep(0.1)

    # --- Task 3: Forward Sarvam transcripts → Flutter client --------------
    #
    # Per-session diagnostics: when reporters complain "I spoke for 10s
    # and nothing showed up live", we need to know whether Sarvam was
    # emitting interim transcripts during that time or whether it only
    # spoke at end-of-utterance. The instrumentation below logs:
    #   - time-to-first-data (latency from session open to first interim)
    #   - total data messages received
    #   - vad_end events received
    # These three numbers tell us Sarvam-side vs mobile-side responsibility.
    async def relay_from_sarvam(s_ws):
        session_started = time.monotonic()
        first_data_at: Optional[float] = None
        data_count = 0
        vad_end_count = 0
        try:
            async for message in s_ws:
                try:
                    if isinstance(message, bytes):
                        await ws.send_bytes(message)
                    else:
                        # Cheap inspection — we already json.loads inside
                        # _rewrite_transcript_message, but we want the raw
                        # type/event before mutation. Parse once here.
                        try:
                            parsed = json.loads(message) if message else None
                        except (ValueError, TypeError):
                            parsed = None
                        if isinstance(parsed, dict):
                            t = parsed.get("type")
                            if t == "data":
                                data_count += 1
                                if first_data_at is None:
                                    first_data_at = time.monotonic()
                                    logger.info(
                                        "STT proxy: first transcript at %.2fs "
                                        "(reporter=%s)",
                                        first_data_at - session_started,
                                        reporter_id,
                                    )
                            elif t == "events":
                                ev = (parsed.get("data") or {}).get("event")
                                if ev == "vad_end":
                                    vad_end_count += 1
                        await ws.send_text(_rewrite_transcript_message(message))
                except Exception:
                    break
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            duration = time.monotonic() - session_started
            ttf = (
                f"{first_data_at - session_started:.2f}s"
                if first_data_at is not None
                else "never"
            )
            logger.info(
                "STT proxy: relay summary (reporter=%s) "
                "duration=%.1fs data_msgs=%d vad_ends=%d ttf=%s",
                reporter_id, duration, data_count, vad_end_count, ttf,
            )

    # --- Main loop: single connection, reconnect only on disconnect -------
    try:
        client_task = asyncio.create_task(read_client())
        sender_task = asyncio.create_task(send_to_sarvam())

        session_num = 0
        while client_alive:
            session_num += 1
            try:
                async with ws_connect(
                    sarvam_url, extra_headers=sarvam_headers, ssl=ssl_ctx
                ) as s_ws:
                    sarvam_ws = s_ws
                    logger.info(f"STT proxy: session #{session_num} opened (reporter={reporter_id})")

                    relay_task = asyncio.create_task(relay_from_sarvam(s_ws))

                    # Wait until relay ends (Sarvam disconnects) or client leaves
                    await relay_task
                    sarvam_ws = None

                    logger.info(f"STT proxy: session #{session_num} ended (reporter={reporter_id})")

            except websockets.exceptions.ConnectionClosed:
                if not client_alive:
                    break
                logger.warning("STT proxy: Sarvam WS closed, reconnecting...")
                await asyncio.sleep(0.2)
            except Exception as exc:
                if not client_alive:
                    break
                logger.error(f"STT proxy: Sarvam error: {exc}, retrying...")
                await asyncio.sleep(0.5)

        # Clean up
        for t in [client_task, sender_task]:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

    except Exception as exc:
        logger.error(f"STT proxy: fatal error: {exc}")
        try:
            await ws.close(code=1011, reason="Upstream STT service unavailable")
        except Exception:
            pass
    finally:
        # Log the streaming STT cost once per session. PCM 16-bit mono @ 16kHz
        # = 32000 bytes/sec. We don't know which story the dictation
        # belongs to (the WS proxy isn't story-aware), so this lands in
        # the "dictation" bucket attributed to the reporter.
        if total_audio_bytes > 0:
            audio_seconds = max(1, total_audio_bytes // 32000)
            duration_ms = int((time.monotonic() - session_started) * 1000)
            try:
                with sarvam_client.cost_context(bucket="dictation", user_id=reporter_id):
                    sarvam_client.log_streaming_stt_cost(
                        model=model,
                        audio_seconds=audio_seconds,
                        duration_ms=duration_ms,
                    )
            except Exception as exc:  # noqa: BLE001 — never fail teardown
                logger.warning("STT proxy: failed to log streaming cost: %s", exc)


# ---------------------------------------------------------------------------
# Always-upload audio pipeline
#
# Every recording (tap or long-press) is uploaded here. Tap-recordings keep
# the audio invisibly on the paragraph (transcription_audio_path) for silent
# reprocessing; long-press recordings additionally surface the audio as a
# playable attachment block (media_path / media_type='audio').
#
# The endpoint is fire-and-forget friendly: client uploads from a background
# queue, server stores the audio, runs STT inline, and returns the transcript.
# If STT fails transiently, the paragraph is marked pending_retry and the
# background sweep will retry — the client never has to care.
# ---------------------------------------------------------------------------


@router.post("/api/stt/upload-audio")
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = FastAPIFile(...),
    story_id: str = Form(...),
    paragraph_id: str = Form(...),
    is_attachment: bool = Form(False),
    language_code: str = Form("od-IN"),
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Persist an audio recording and queue background STT.

    Returns as soon as the audio is saved and the paragraph is updated with
    the audio URL — STT runs as a background task so a slow Sarvam call
    never blocks the client. The realtime transcript the user sees comes
    from the live WS proxy (``/ws/stt``); this endpoint is purely the
    safety-net path that gives us audio-on-file and a server-side transcript
    we can use to silently fix bad/empty live results.

    Behaviour:
      * Audio bytes are written to GCS (or local in dev) under ``audio/``.
      * The paragraph identified by ``paragraph_id`` inside ``story_id`` gets
        ``transcription_audio_path`` populated (always) and, when
        ``is_attachment=True``, also ``media_path`` / ``media_type='audio'``
        so the editor renders a playable audio block.
      * STT runs after the response. On success the paragraph's text is
        overwritten only if (a) STT returned non-empty AND (b) the existing
        text is empty — we never clobber a transcript the user can already
        see from the live WS path.
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Empty audio file",
        )
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Audio file too large (max 25 MB)",
        )

    story = (
        db.query(Story)
        .filter(
            Story.id == story_id,
            Story.organization_id == org_id,
            Story.reporter_id == user.id,
            Story.deleted_at.is_(None),
        )
        .first()
    )
    if story is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )

    paragraphs = list(story.paragraphs or [])
    target_idx = next(
        (i for i, p in enumerate(paragraphs) if isinstance(p, dict) and p.get("id") == paragraph_id),
        None,
    )
    if target_idx is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Paragraph {paragraph_id} not found in story",
        )

    # 1. Persist audio
    filename = file.filename or "audio.m4a"
    audio_url = save_file(contents, filename, subfolder="audio")

    # 2. Update paragraph fields that don't depend on STT (audio path,
    #    optional attachment, "pending" status). Commit immediately so the
    #    response can return without blocking on Sarvam.
    from sqlalchemy.orm.attributes import flag_modified

    paragraph = dict(paragraphs[target_idx])
    paragraph["transcription_audio_path"] = audio_url
    paragraph["transcription_status"] = "pending"
    paragraph["transcription_language"] = language_code
    if is_attachment:
        paragraph["media_path"] = audio_url
        paragraph["media_type"] = "audio"
        paragraph["media_name"] = filename
    paragraphs[target_idx] = paragraph

    story.paragraphs = paragraphs
    story.updated_at = now_ist()
    story.refresh_search_text()
    flag_modified(story, "paragraphs")
    db.commit()

    # 3. Queue STT for after-response. The task opens its own DB session,
    #    re-reads the paragraph, and writes the transcript only if safe.
    background_tasks.add_task(
        _run_stt_in_background,
        story_id=story_id,
        paragraph_id=paragraph_id,
        audio_bytes=contents,
        filename=filename,
        language_code=language_code,
        user_id=user.id,
        # Pass through the validated org so the helper re-checks before
        # the write. Belt + suspenders against future callers that
        # forget to validate the story upfront.
        expected_org_id=org_id,
    )

    return {
        "transcription_status": "pending",
        "audio_url": audio_url,
        "is_attachment": is_attachment,
    }


def _run_stt_in_background(
    story_id: str,
    paragraph_id: str,
    audio_bytes: bytes,
    filename: str,
    language_code: str,
    user_id: Optional[str] = None,
    expected_org_id: Optional[str] = None,
) -> None:
    """Background task: run STT and update paragraph in a fresh DB session.

    [expected_org_id] is the organization the calling endpoint already
    validated this story belongs to. We re-check inside the helper as
    defense-in-depth: if a future caller forgets to validate before
    queueing this task, the helper will quietly drop a misrouted
    update rather than scribbling on a story in a different org.
    """
    import asyncio as _asyncio
    from ..database import SessionLocal

    async def _do_stt() -> str:
        # cost_context must be set on the same task as the Sarvam call so
        # the wrapper can read it via contextvar. Setting here (inside the
        # background task's own event loop) makes the STT charge land on
        # this story.
        with sarvam_client.cost_context(story_id=story_id, user_id=user_id):
            return await stt_service.transcribe_audio(
                audio_bytes,
                filename=filename,
                language_code=language_code,
            )

    transcript = ""
    new_status = "ok"
    try:
        transcript = _asyncio.run(_do_stt())
    except stt_service.SttRetryable as exc:
        logger.warning(
            "Background STT transient failure (paragraph=%s story=%s): %s — pending_retry",
            paragraph_id, story_id, exc,
        )
        new_status = "pending_retry"
    except stt_service.SttError as exc:
        logger.error(
            "Background STT permanent failure (paragraph=%s story=%s): %s",
            paragraph_id, story_id, exc,
        )
        new_status = "failed"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Background STT unexpected error: %s", exc)
        new_status = "pending_retry"

    db = SessionLocal()
    try:
        story_q = db.query(Story).filter(Story.id == story_id)
        if expected_org_id is not None:
            story_q = story_q.filter(Story.organization_id == expected_org_id)
        story = story_q.first()
        if story is None:
            # Either deleted, or org mismatch (defense-in-depth). The
            # second case is silently dropped — we don't want a noisy
            # log for what should be a never-happens condition.
            logger.warning("Background STT: story %s gone or wrong org", story_id)
            return
        paragraphs = list(story.paragraphs or [])
        idx = next(
            (i for i, p in enumerate(paragraphs) if isinstance(p, dict) and p.get("id") == paragraph_id),
            None,
        )
        if idx is None:
            logger.info("Background STT: paragraph %s removed before STT finished", paragraph_id)
            return
        paragraph = dict(paragraphs[idx])
        paragraph["transcription_status"] = new_status
        paragraph["transcription_attempts"] = (paragraph.get("transcription_attempts") or 0) + 1
        # Only fill in text when (a) STT succeeded and (b) the user's live
        # transcript path didn't already populate it. Never clobber what
        # the user can already see in the editor.
        if transcript and not (paragraph.get("text") or "").strip():
            paragraph["text"] = transcript
        paragraphs[idx] = paragraph

        story.paragraphs = paragraphs
        story.updated_at = now_ist()
        story.refresh_search_text()
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(story, "paragraphs")
        db.commit()
    finally:
        db.close()


@router.post("/api/stt/retranscribe")
async def retranscribe_paragraph(
    story_id: str = Form(...),
    paragraph_id: str = Form(...),
    language_code: str = Form("od-IN"),
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    """Re-run STT against a paragraph's stored audio.

    The reporter taps "Retranscribe" when the live transcript came back wrong
    or empty. We pull the audio from ``transcription_audio_path`` (set by the
    upload endpoint), re-run Sarvam, and overwrite the paragraph text.
    """
    story = (
        db.query(Story)
        .filter(
            Story.id == story_id,
            Story.organization_id == org_id,
            Story.reporter_id == user.id,
            Story.deleted_at.is_(None),
        )
        .first()
    )
    if story is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Story not found")

    paragraphs = list(story.paragraphs or [])
    target_idx = next(
        (i for i, p in enumerate(paragraphs) if isinstance(p, dict) and p.get("id") == paragraph_id),
        None,
    )
    if target_idx is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Paragraph {paragraph_id} not found in story",
        )

    paragraph = dict(paragraphs[target_idx])
    audio_url = paragraph.get("transcription_audio_path") or paragraph.get("media_path")
    if not audio_url:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="No audio available for this paragraph",
        )

    audio_bytes = await _fetch_audio_bytes(audio_url)
    if not audio_bytes:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Could not load saved audio",
        )

    try:
        transcript = await stt_service.transcribe_audio(
            audio_bytes,
            filename=os.path.basename(audio_url) or "audio.m4a",
            language_code=language_code,
        )
    except stt_service.SttRetryable as exc:
        logger.warning("Retranscribe transient failure: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transcription service temporarily unavailable — please try again",
        )
    except stt_service.SttError as exc:
        logger.error("Retranscribe permanent failure: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail=f"Transcription failed: {exc}",
        )

    paragraph["text"] = transcript
    paragraph["transcription_status"] = "ok"
    paragraph["transcription_attempts"] = (paragraph.get("transcription_attempts") or 0) + 1
    paragraphs[target_idx] = paragraph

    story.paragraphs = paragraphs
    story.updated_at = now_ist()
    story.refresh_search_text()
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(story, "paragraphs")
    db.commit()

    return {"transcript": transcript, "transcription_status": "ok"}


async def _fetch_audio_bytes(audio_url: str) -> bytes:
    """Pull audio bytes back from wherever ``save_file`` parked them.

    GCS URLs are public-readable in our setup; local /uploads paths are
    relative to UPLOAD_DIR.
    """
    if audio_url.startswith("http://") or audio_url.startswith("https://"):
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(audio_url)
            if resp.status_code != 200:
                logger.warning("Audio fetch %d for %s", resp.status_code, audio_url)
                return b""
            return resp.content
    # Local: strip leading /uploads/ and resolve relative to UPLOAD_DIR
    from ..services.storage import UPLOAD_DIR
    rel = audio_url.lstrip("/").removeprefix("uploads/")
    path = os.path.join(UPLOAD_DIR, rel)
    if not os.path.exists(path):
        return b""
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Batch transcription endpoint
#
# Replaces the WebSocket streaming path for mobile v2. The app records
# locally (with on-device DTLN denoising + optional speaker verification),
# trims silence client-side, then uploads the full audio here for a SINGLE
# Gemini call. Advantages over the streaming path:
#   - ~7× cheaper (system instruction sent once, not per 4 s chunk)
#   - Better accuracy (Gemini sees full context, no chunk-boundary splits)
#   - Simpler code (no WebSocket reconnect, no sliding-window state)
#   - No hallucination feedback loops (no cumulative transcript echo)
# ---------------------------------------------------------------------------

# Cap batch output tokens. A 10 min recording at normal Odia speech pace
# transcribes to ~2000–3000 tokens; 8000 gives generous headroom for
# dense/fast speakers or code-mixed segments.
_BATCH_MAX_OUTPUT_TOKENS = 8000


@router.post("/api/stt/transcribe")
async def transcribe_batch(
    file: UploadFile = FastAPIFile(...),
    language_code: str = Form("od-IN"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transcribe a complete audio recording in a single Gemini call.

    The mobile app records locally, applies on-device DTLN denoising and
    optional client-side VAD trimming, then uploads the WAV here. We run
    a server-side VAD pass (defence-in-depth), call Gemini once with the
    full audio, and return the transcript synchronously.

    Returns:
        ``{"transcript": "...", "status": "ok"|"silence", "audio_seconds": float}``
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Empty audio file",
        )
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Audio file too large (max 25 MB)",
        )

    # ── Quota gate ────────────────────────────────────────────────────
    if transcription_quota.is_over_quota(db, user):
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Monthly transcription quota exhausted",
        )

    # ── Extract PCM from WAV ──────────────────────────────────────────
    # Mobile sends 16 kHz 16-bit mono WAV. Strip the 44-byte header to
    # get raw PCM for VAD compression.
    pcm_bytes = contents
    if contents[:4] == b"RIFF" and contents[8:12] == b"WAVE":
        # Standard WAV: data chunk starts after the header. Find the
        # "data" sub-chunk rather than assuming a fixed 44-byte offset
        # (some encoders add extra chunks before data).
        data_offset = contents.find(b"data")
        if data_offset != -1:
            # 4 bytes "data" + 4 bytes chunk-size → PCM starts at +8
            pcm_bytes = contents[data_offset + 8:]
        else:
            pcm_bytes = contents[44:]  # fallback: assume minimal header

    # ── Audio duration ───────────────────────────────────────────────
    # The mobile client already runs client-side VAD trimming before
    # uploading. Running server-side VAD again is destructive — the
    # double-pass aggressively strips speech that was already at reduced
    # amplitude due to DTLN denoising + OS noise suppression. We trust
    # the client-side trim and send the full received audio to Gemini.
    # The only gate we keep is a minimum-length check to reject truly
    # empty recordings.
    raw_audio_seconds = len(pcm_bytes) / _PCM_BYTES_PER_SEC

    logger.info(
        "STT: reporter=%s, audio=%.1fs, lang=%s",
        user.id, raw_audio_seconds, language_code,
    )

    # Too short — nothing to transcribe (< 0.6s of audio)
    if len(pcm_bytes) < _VAD_MIN_SPEECH_BYTES:
        return {"transcript": "", "status": "silence", "audio_seconds": 0.0}

    # ── Gemini call ──────────────────────────────────────────────────
    wav = _wrap_pcm_as_wav(pcm_bytes)
    audio_seconds = raw_audio_seconds
    primary_model = settings.STT_GEMINI_MODEL
    usage_sink: list[dict] = []

    try:
        text = await gemini_client.stt(
            audio_bytes=wav,
            mime_type="audio/wav",
            language_code=language_code,
            model=primary_model,
            max_tokens=_BATCH_MAX_OUTPUT_TOKENS,
            usage_sink=usage_sink,
            timeout=120.0,
        )
    except Exception as exc:
        logger.error(
            "STT Gemini call failed (reporter=%s, audio=%.1fs): %r",
            user.id, audio_seconds, exc,
        )
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Transcription failed — please try again",
        )

    # ── Quality gate + fallback ───────────────────────────────────────
    primary_usage = usage_sink[-1] if usage_sink else {}
    primary_output_tokens = int(primary_usage.get("output_tokens") or 0)
    primary_failure = _check_chunk_quality(
        text or "",
        audio_seconds=audio_seconds,
        output_tokens=primary_output_tokens,
        expected_script_lang=language_code,
    )

    flash_fallback_used = False
    # Escalate to the stronger model when: (a) quality gate failed, OR
    # (b) the primary returned an empty transcript for non-trivial audio
    # (≥ 2s). Flash-Lite sometimes returns 0 output tokens on audio that
    # survived client-side VAD — that's a model failure, not silence.
    needs_fallback = bool(primary_failure) or (
        not (text or "").strip()
        and audio_seconds >= 2.0
    )
    if needs_fallback and primary_model != _STT_FALLBACK_MODEL:
        reason = primary_failure or "empty_transcript"
        logger.info(
            "STT: escalating to %s (%s on %s, reporter=%s)",
            _STT_FALLBACK_MODEL, reason, primary_model, user.id,
        )
        try:
            fallback_text = await gemini_client.stt(
                audio_bytes=wav,
                mime_type="audio/wav",
                language_code=language_code,
                model=_STT_FALLBACK_MODEL,
                max_tokens=_BATCH_MAX_OUTPUT_TOKENS,
                usage_sink=usage_sink,
                timeout=120.0,
            )
            flash_fallback_used = True
            fb_usage = usage_sink[-1] if usage_sink else {}
            fb_output_tokens = int(fb_usage.get("output_tokens") or 0)
            fb_failure = _check_chunk_quality(
                fallback_text or "",
                audio_seconds=audio_seconds,
                output_tokens=fb_output_tokens,
                expected_script_lang=language_code,
            )
            if fb_failure:
                logger.warning(
                    "STT: fallback also failed quality (%s) — "
                    "returning primary output anyway (reporter=%s)",
                    fb_failure, user.id,
                )
                # For batch, return the primary output rather than empty —
                # the reporter can see and manually correct it.
            else:
                text = fallback_text
        except Exception as exc:
            logger.warning(
                "STT fallback to %s failed: %r — using primary output",
                _STT_FALLBACK_MODEL, exc,
            )

    # ── Post-processing ───────────────────────────────────────────────
    text = name_registry.replace_english_names((text or "").strip())
    text, runs_collapsed = _collapse_runaway_repetition(text)
    if runs_collapsed:
        logger.info("STT: collapsed %d repetition run(s) (reporter=%s)", runs_collapsed, user.id)
    text, was_hallucinated = _filter_hallucinations(text)
    if was_hallucinated:
        logger.info("STT: filtered hallucination (reporter=%s)", user.id)

    # ── Telemetry ─────────────────────────────────────────────────────
    total_cost = sum(float(u.get("cost_inr") or 0) for u in usage_sink)
    total_input = sum(int(u.get("input_tokens") or 0) for u in usage_sink)
    total_output = sum(int(u.get("output_tokens") or 0) for u in usage_sink)
    logger.info(
        "STT done (reporter=%s, audio=%.1fs, "
        "flash_fallback=%s, cost=₹%.4f, in=%d, out=%d)",
        user.id, raw_audio_seconds,
        flash_fallback_used, total_cost, total_input, total_output,
    )

    # ── Quota usage ───────────────────────────────────────────────────
    # Count mic-on seconds (raw, not post-VAD) so the reporter's
    # perception of "I spoke for X minutes" matches the quota drain.
    used_seconds = int(round(raw_audio_seconds))
    if used_seconds > 0:
        transcription_quota.add_usage(db, user_id=user.id, seconds=used_seconds)

    return {
        "transcript": text or "",
        "status": "ok" if text else "silence",
        "audio_seconds": round(raw_audio_seconds, 1),
    }


# ---------------------------------------------------------------------------
# Task 3 – REST LLM chat proxy
# ---------------------------------------------------------------------------

# Odia Unicode range: U+0B00–U+0B7F
def _is_predominantly_odia(text: str, threshold: float = 0.4) -> bool:
    """Return True if at least `threshold` fraction of letters are Odia script.

    Counts any char in the Odia Unicode block (including vowel signs and
    nukta) as Odia, and counts those plus ASCII alphabetic chars as letters.
    """
    if not text:
        return False
    odia = sum(1 for c in text if "\u0B00" <= c <= "\u0B7F")
    other_letters = sum(1 for c in text if c.isalpha() and not ("\u0B00" <= c <= "\u0B7F"))
    total = odia + other_letters
    if total == 0:
        return False
    return (odia / total) >= threshold


class ChatRequest(BaseModel):
    messages: list[dict] = Field(..., max_length=20)
    model: str = "sarvam-30b"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = Field(None, le=8192)
    # Optional — when the call is on behalf of a specific story (e.g. the
    # review-page editor invoking an AI assist), the panel can pass it so
    # the cost lands on the story instead of a generic bucket. Backend-only
    # — purely for cost attribution; not surfaced anywhere user-facing.
    story_id: Optional[str] = None


@router.post("/api/llm/chat")
async def llm_chat(
    body: ChatRequest,
    # _lite variant releases the DB connection before the LLM await — see
    # deps.get_current_user_lite for why this matters on long-running endpoints.
    user: User = Depends(get_current_user_lite),
):
    """Proxy chat completion requests to Sarvam AI so the Flutter client
    never needs the API key."""

    # Inject no-markdown instruction into system prompt
    NO_MARKDOWN = "Do not output markdown formatting (no **, ##, -, etc). Return plain text only."
    messages = list(body.messages)
    if messages and messages[0].get("role") == "system":
        messages[0] = {**messages[0], "content": messages[0]["content"] + "\n\n" + NO_MARKDOWN}
    else:
        messages.insert(0, {"role": "system", "content": NO_MARKDOWN})

    # Map legacy model name to current model
    model = body.model
    if model == "sarvam-m":
        model = "sarvam-30b"

    # Attribution: prefer story_id when given, otherwise generic
    # reviewer_panel bucket. Either way we tag the user so we can answer
    # "which reviewer ran the AI bill up this week".
    attribution = (
        sarvam_client.cost_context(story_id=body.story_id, user_id=user.id)
        if body.story_id
        else sarvam_client.cost_context(bucket="reviewer_panel", user_id=user.id)
    )

    # Convert OpenAI-style messages to Gemini's (system + single-turn
    # user prompt). Multi-turn assistant history is rare on this
    # endpoint — when present, fold prior assistant turns into the user
    # prompt as bracketed context so a Gemini call still sees them.
    system_parts: list[str] = []
    prompt_parts: list[str] = []
    for m in messages:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
        elif role == "user":
            prompt_parts.append(content)
        elif role == "assistant":
            prompt_parts.append(f"[Previous assistant turn: {content}]")
    system = "\n\n".join(system_parts) or None
    prompt = "\n\n".join(prompt_parts) or " "
    max_tokens = min(body.max_tokens or 4096, 8192)
    temperature = body.temperature if body.temperature is not None else None

    try:
        from ..services import gemini_client
        with attribution:
            text = await gemini_client.chat(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=60.0,
            )
        # Wrap in the OpenAI-shape the mobile/panel clients already
        # parse — they read data.choices[0].message.content. Keeping
        # the response shape stable means no client release needed.
        return {
            "model": settings.GEMINI_DEFAULT_MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text.strip()},
                    "finish_reason": "stop",
                }
            ],
        }
    except Exception as exc:  # noqa: BLE001 — gemini_client wraps everything
        from fastapi.responses import JSONResponse
        logger.warning(
            "/api/llm/chat: Gemini call failed (max_tokens=%s, msgs=%d): %s",
            body.max_tokens, len(messages), exc,
        )
        return JSONResponse(
            status_code=502,
            content={"detail": f"LLM call failed: {exc}"},
        )


# ---------------------------------------------------------------------------
# Translate proxy — Sarvam dedicated /translate endpoint (mayura:v1)
#
# Why this exists alongside /api/llm/chat: the chat-completions LLM
# (sarvam-30b) is unreliable for "translate to English" — it sometimes
# returns the source Odia even with retries. Sarvam's /translate is purpose-
# built for translation and respects target language deterministically.
# Limit: 1000 chars per request, so we chunk by paragraph.
# ---------------------------------------------------------------------------

_TRANSLATE_CHUNK_LIMIT = 950  # leave a bit of headroom under Sarvam's 1000


class TranslateRequest(BaseModel):
    text: str = Field(..., max_length=200_000)
    source_language_code: str = "od-IN"
    target_language_code: str = "en-IN"
    mode: str = "formal"  # formal | classic-colloquial | modern-colloquial | code-mixed
    # Optional — see ChatRequest.story_id. When the panel translates an
    # article body for the editor it should pass story.id so the per-story
    # cost rollup includes translate spend (this is usually the largest
    # per-story line item).
    story_id: Optional[str] = None


def _hard_split(text: str, limit: int) -> list[str]:
    """Last-resort: cut on whitespace nearest to `limit`, else hard-cut."""
    out: list[str] = []
    remaining = text
    while len(remaining) > limit:
        # Prefer cutting on a space within the last 20% of the window
        cut = remaining.rfind(" ", int(limit * 0.8), limit)
        if cut <= 0:
            cut = limit
        out.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()
    if remaining.strip():
        out.append(remaining.strip())
    return out


def _chunk_for_translate(text: str, limit: int = _TRANSLATE_CHUNK_LIMIT) -> list[str]:
    """Split text into <=`limit`-char chunks on paragraph → sentence → word boundaries."""
    chunks: list[str] = []
    for paragraph in text.split("\n\n"):
        if not paragraph.strip():
            continue
        if len(paragraph) <= limit:
            chunks.append(paragraph)
            continue
        # Paragraph too long — split on sentence boundaries (। or .)
        buf = ""
        for sentence in re.split(r"(?<=[।.!?])\s+", paragraph):
            if not sentence:
                continue
            # A single sentence may itself exceed the limit (no punctuation
            # in long Odia text). Hard-split it on whitespace as fallback.
            if len(sentence) > limit:
                if buf.strip():
                    chunks.append(buf.strip())
                    buf = ""
                chunks.extend(_hard_split(sentence, limit))
                continue
            if len(buf) + len(sentence) + 1 > limit and buf:
                chunks.append(buf.strip())
                buf = sentence
            else:
                buf = f"{buf} {sentence}".strip() if buf else sentence
        if buf.strip():
            chunks.append(buf.strip())
    return chunks


@router.post("/api/llm/translate")
async def llm_translate(
    body: TranslateRequest,
    user: User = Depends(get_current_user),
):
    """Translate text using Sarvam's dedicated /translate endpoint.

    Chunks the input on paragraph/sentence boundaries (Sarvam caps each
    request at 1000 chars), translates each chunk, then rejoins with the
    original paragraph separators preserved.
    """
    chunks = _chunk_for_translate(body.text)
    if not chunks:
        return {"translated_text": ""}

    attribution = (
        sarvam_client.cost_context(story_id=body.story_id, user_id=user.id)
        if body.story_id
        else sarvam_client.cost_context(bucket="reviewer_panel", user_id=user.id)
    )
    translated_chunks: list[str] = []
    # Map BCP-47 language codes to plain English names for the
    # Gemini prompt (the underlying chat is more reliable with names
    # than codes).
    _LANG_NAMES = {
        "od-IN": "Odia", "en-IN": "English", "en-US": "English",
        "hi-IN": "Hindi", "bn-IN": "Bengali", "te-IN": "Telugu",
        "ta-IN": "Tamil", "mr-IN": "Marathi", "gu-IN": "Gujarati",
    }
    src_lang = _LANG_NAMES.get(body.source_language_code, body.source_language_code)
    tgt_lang = _LANG_NAMES.get(body.target_language_code, body.target_language_code)

    from ..services import gemini_client
    with attribution:
        for chunk in chunks:
            try:
                translated = (await gemini_client.translate(
                    text=chunk,
                    source_lang=src_lang,
                    target_lang=tgt_lang,
                    timeout=60.0,
                )).strip()
                translated_chunks.append(translated)
            except Exception as exc:  # noqa: BLE001
                from fastapi.responses import JSONResponse
                logger.warning(
                    "/api/llm/translate: Gemini call failed (chunk_len=%d, src=%s, tgt=%s): %s",
                    len(chunk), src_lang, tgt_lang, exc,
                )
                return JSONResponse(
                    status_code=502,
                    content={"detail": f"Translate failed: {exc}"},
                )

    return {"translated_text": "\n\n".join(translated_chunks)}


# ---------------------------------------------------------------------------
# Task 4 – OCR via Sarvam Document Intelligence
# ---------------------------------------------------------------------------

# STT uses "od-IN" for Odia, but Document Intelligence uses "or-IN".
_DI_LANGUAGE_MAP = {
    "od-IN": "or-IN",
}


def _strip_analysis_text(text: str) -> str:
    """Remove AI-generated image analysis/description lines from OCR output.

    Sarvam DI sometimes includes English descriptions like "The image shows a
    newspaper article..." alongside the actual extracted text.  These lines are
    detected by being predominantly ASCII with no Odia characters.
    """
    # Don't touch anything inside <table> blocks
    table_pattern = re.compile(r'<table[\s\S]*?</table>', re.IGNORECASE)
    tables: list[tuple[int, int]] = [(m.start(), m.end()) for m in table_pattern.finditer(text)]

    def _in_table(pos: int) -> bool:
        return any(s <= pos < e for s, e in tables)

    odia_re = re.compile(r'[\u0B00-\u0B7F]')
    # Common analysis sentence starters
    analysis_re = re.compile(
        r'^\s*(The |This |It |These |Here |There |An? |Note:)',
        re.IGNORECASE,
    )

    lines = text.split('\n')
    cleaned: list[str] = []
    offset = 0
    for line in lines:
        line_start = text.index(line, offset) if line else offset
        offset = line_start + len(line) + 1  # +1 for newline

        if _in_table(line_start):
            cleaned.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue

        # Check if line has Odia characters — always keep
        if odia_re.search(stripped):
            cleaned.append(line)
            continue

        # Check if line is predominantly ASCII (likely analysis text)
        ascii_count = sum(1 for c in stripped if ord(c) < 128)
        if len(stripped) > 10 and ascii_count / len(stripped) > 0.8:
            # Likely English analysis — skip it
            continue

        # Check for common analysis patterns
        if analysis_re.match(stripped):
            continue

        cleaned.append(line)

    return '\n'.join(cleaned)


def _parse_html_table(html: str) -> list[list[str]]:
    """Parse an HTML <table> block into a 2D list of cell strings."""
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
    result: list[list[str]] = []
    for row_html in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row_html, re.DOTALL | re.IGNORECASE)
        # Strip any inner HTML tags and normalize whitespace
        result.append([
            re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip()
            for c in cells
        ])
    # Drop empty rows
    return [r for r in result if any(cell for cell in r)]


def _split_ocr_segments(text: str) -> list[dict]:
    """Split OCR text into segments of type 'text' or 'table'.

    HTML <table> blocks become table segments with parsed 2D cell data.
    Everything else becomes text segments.
    """
    table_pattern = re.compile(r'(<table[\s\S]*?</table>)', re.IGNORECASE)
    parts = table_pattern.split(text)
    segments: list[dict] = []

    for part in parts:
        if table_pattern.match(part):
            table_data = _parse_html_table(part)
            if table_data:
                segments.append({
                    "type": "table",
                    "text": "",
                    "table_data": table_data,
                })
        else:
            # Strip markdown artifacts: headers, bold, etc.
            cleaned = part.strip()
            cleaned = re.sub(r'^#{1,6}\s+', '', cleaned, flags=re.MULTILINE)  # headers
            cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)  # bold
            cleaned = re.sub(r'\*(.*?)\*', r'\1', cleaned)  # italic
            cleaned = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', cleaned)  # images
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
            if cleaned:
                segments.append({
                    "type": "text",
                    "text": cleaned,
                    "table_data": None,
                })

    return segments


def _run_ocr_job(image_bytes: bytes, filename: str, language: str) -> dict:
    """Run Sarvam Document Intelligence OCR synchronously (called via to_thread).

    Creates a DI job, uploads the image, processes it, and returns
    structured segments (text + tables).
    """
    from sarvamai import SarvamAI

    client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)

    # Normalize language code for Document Intelligence API
    language = _DI_LANGUAGE_MAP.get(language, language)

    # DI API only accepts PDF or ZIP — wrap the image in a ZIP
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    upload_zip_path = None
    output_dir = tempfile.mkdtemp()
    output_zip = os.path.join(output_dir, "output.zip")

    ocr_started = time.monotonic()
    try:
        # Create a ZIP containing the image
        upload_zip_fd, upload_zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(upload_zip_fd)
        with zipfile.ZipFile(upload_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"image{ext}", image_bytes)

        job = client.document_intelligence.create_job(
            language=language,
            output_format="md",
        )
        job.upload_file(upload_zip_path)
        job.start()
        job.wait_until_complete(timeout=120)
        job.download_output(output_zip)

        # Cost: ₹1.5 per page. Single image = 1 page (the SDK doesn't
        # expose a page count for image inputs). For PDF inputs this
        # would need to be the actual page count.
        try:
            sarvam_client.log_vision_cost(
                pages=1,
                duration_ms=int((time.monotonic() - ocr_started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 — never break the OCR caller
            logger.warning("OCR: failed to log vision cost: %s", exc)

        # Parse the markdown from the output ZIP
        extracted_text = ""
        with zipfile.ZipFile(output_zip, "r") as zf:
            for name in sorted(zf.namelist()):
                if name.endswith(".md"):
                    extracted_text += zf.read(name).decode("utf-8", errors="replace")
                    extracted_text += "\n"

        # Strip embedded base64 images from the markdown output.
        extracted_text = re.sub(
            r'!\[[^\]]*\]\(data:[^)]+\)', '', extracted_text
        )
        extracted_text = re.sub(
            r'data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+', '', extracted_text
        )
        extracted_text = re.sub(r'\n{3,}', '\n\n', extracted_text)

        # Strip analysis text and split into structured segments
        cleaned = _strip_analysis_text(extracted_text.strip())
        segments = _split_ocr_segments(cleaned)

        # Build plain-text fallback (tables flattened to tab-separated)
        plain_parts: list[str] = []
        for seg in segments:
            if seg["type"] == "table" and seg.get("table_data"):
                for row in seg["table_data"]:
                    plain_parts.append("\t".join(row))
            elif seg.get("text"):
                plain_parts.append(seg["text"])

        return {
            "text": "\n".join(plain_parts).strip(),
            "segments": segments,
        }

    finally:
        # Clean up temp files
        if upload_zip_path:
            try:
                os.unlink(upload_zip_path)
            except OSError:
                pass
        try:
            for f in os.listdir(output_dir):
                os.unlink(os.path.join(output_dir, f))
            os.rmdir(output_dir)
        except OSError:
            pass


class OcrSegment(BaseModel):
    type: str = "text"
    text: str = ""
    table_data: Optional[list[list[str]]] = None


class OcrResponse(BaseModel):
    text: str
    segments: list[OcrSegment] = []
    language: str


@router.post("/api/ocr", response_model=OcrResponse)
async def ocr_image(
    file: UploadFile = FastAPIFile(...),
    language: str = "od-IN",
    user: User = Depends(get_current_user),
):
    """Run OCR on an uploaded image using Sarvam Document Intelligence.

    Accepts PNG, JPG, JPEG, WEBP images. Returns extracted text with
    structured segments (text blocks + parsed tables).
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"}
    if ext not in allowed:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {ext} not supported for OCR. Use: {', '.join(sorted(allowed))}",
        )

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large (max 20 MB)",
        )

    try:
        result = await asyncio.to_thread(
            _run_ocr_job, contents, file.filename or "image.jpg", language
        )
    except Exception as exc:
        logger.error(f"OCR failed: {exc}")
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=502,
            content={"detail": f"OCR processing failed: {str(exc)}"},
        )

    return OcrResponse(
        text=result["text"],
        segments=[OcrSegment(**seg) for seg in result["segments"]],
        language=language,
    )
