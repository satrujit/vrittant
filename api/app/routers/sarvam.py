import asyncio
import json
import logging
import os
import re
import ssl
import tempfile
import time
import zipfile
from typing import Optional

import certifi
import httpx
import websockets.exceptions
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, File as FastAPIFile, WebSocket, WebSocketDisconnect, status as http_status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_org_id
from ..models.story import Story
from ..services import stt as stt_service
from ..services.storage import save_file
from ..utils.tz import now_ist

# Use the legacy connect API (compatible with how Sarvam SDK connects)
try:
    from websockets.legacy.client import connect as ws_connect
except ImportError:
    from websockets import connect as ws_connect
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from ..config import settings
from ..deps import get_current_user
from ..models.user import User
from ..services import name_registry, sarvam_client

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
    async def relay_from_sarvam(s_ws):
        try:
            async for message in s_ws:
                try:
                    if isinstance(message, bytes):
                        await ws.send_bytes(message)
                    else:
                        await ws.send_text(_rewrite_transcript_message(message))
                except Exception:
                    break
        except websockets.exceptions.ConnectionClosed:
            pass

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
) -> None:
    """Background task: run STT and update paragraph in a fresh DB session."""
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
        story = db.query(Story).filter(Story.id == story_id).first()
        if story is None:
            logger.warning("Background STT: story %s gone", story_id)
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
    user: User = Depends(get_current_user),
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
