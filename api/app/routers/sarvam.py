import asyncio
import logging
import os
import re
import ssl
import tempfile
import zipfile
from typing import Optional

import certifi
import httpx
import websockets.exceptions
from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, WebSocket, WebSocketDisconnect

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

    # --- Task 1: Read from Flutter client, enqueue audio chunks -----------
    async def read_client():
        nonlocal client_alive
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.receive":
                    payload = msg.get("text") or msg.get("bytes")
                    if payload:
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
            if sarvam_ws is not None:
                try:
                    await sarvam_ws.send(chunk)
                except websockets.exceptions.ConnectionClosed:
                    # Re-queue so reconnect loop can replay it
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
                        await ws.send_text(message)
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

    payload = {
        "model": model,
        "messages": messages,
    }
    if body.temperature is not None:
        payload["temperature"] = body.temperature
    if body.max_tokens is not None:
        # Sarvam pro tier caps sarvam-30b at 8192 output tokens
        payload["max_tokens"] = min(body.max_tokens, 8192)

    url = f"{settings.SARVAM_BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.SARVAM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            # Strip <think>/<thinking> reasoning tags from model output
            for choice in data.get("choices", []):
                msg = choice.get("message", {})
                if msg.get("content"):
                    content = msg["content"]
                    content = re.sub(r'<think(?:ing)?>[\s\S]*?</think(?:ing)?>', '', content)
                    content = re.sub(r'<think(?:ing)?>[\s\S]*', '', content)
                    msg["content"] = content.strip()
            return data
        except httpx.HTTPStatusError as exc:
            from fastapi.responses import JSONResponse

            # Log upstream error so we can diagnose 4xx/5xx from Sarvam.
            # Truncate to keep logs readable; full body still goes to client.
            body_preview = exc.response.text[:500]
            logger.warning(
                "Sarvam /v1/chat/completions returned %s (model=%s, max_tokens=%s, msgs=%d): %s",
                exc.response.status_code, model, body.max_tokens,
                len(messages), body_preview,
            )
            return JSONResponse(
                status_code=exc.response.status_code,
                content=exc.response.json()
                if exc.response.headers.get("content-type", "").startswith("application/json")
                else {"detail": exc.response.text},
            )
        except httpx.RequestError:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=502,
                content={"detail": "Unable to reach Sarvam AI service"},
            )


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
