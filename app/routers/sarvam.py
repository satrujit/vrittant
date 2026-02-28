import asyncio
import logging
import ssl
from typing import Optional

import certifi
import httpx
import websockets.exceptions
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

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
    """Zero-buffering bidirectional relay between the Flutter client and
    Sarvam's streaming speech-to-text WebSocket endpoint."""

    # 1. Authenticate
    reporter_id = _authenticate_ws(token)
    if reporter_id is None:
        await ws.close(code=4001, reason="Invalid or missing token")
        return

    await ws.accept()
    logger.info(f"STT proxy: client connected (reporter={reporter_id}, lang={language_code}, model={model})")

    # 2. Build Sarvam WS URL (note: Sarvam uses "language-code" with hyphen)
    sarvam_url = (
        f"wss://api.sarvam.ai/speech-to-text/ws"
        f"?language-code={language_code}&model={model}"
    )
    sarvam_headers = {"api-subscription-key": settings.SARVAM_API_KEY}

    try:
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        async with ws_connect(
            sarvam_url, extra_headers=sarvam_headers, ssl=ssl_ctx
        ) as sarvam_ws:

            async def client_to_sarvam():
                """Forward messages from the Flutter client to Sarvam."""
                try:
                    while True:
                        msg = await ws.receive()
                        if msg["type"] == "websocket.receive":
                            if "text" in msg and msg["text"]:
                                await sarvam_ws.send(msg["text"])
                            elif "bytes" in msg and msg["bytes"]:
                                await sarvam_ws.send(msg["bytes"])
                        elif msg["type"] == "websocket.disconnect":
                            break
                except WebSocketDisconnect:
                    pass

            async def sarvam_to_client():
                """Forward transcription messages from Sarvam back to the client."""
                try:
                    async for message in sarvam_ws:
                        if isinstance(message, bytes):
                            await ws.send_bytes(message)
                        else:
                            await ws.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    pass

            # Run both directions concurrently; when either finishes, clean up.
            tasks = [
                asyncio.create_task(client_to_sarvam()),
                asyncio.create_task(sarvam_to_client()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in pending:
                task.cancel()
            # Await cancelled tasks to suppress warnings
            for task in pending:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except Exception as exc:
        logger.error(f"STT proxy: upstream connection failed: {exc}")
        try:
            await ws.close(code=1011, reason="Upstream STT service unavailable")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Task 3 – REST LLM chat proxy
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    messages: list[dict] = Field(..., max_length=20)
    model: str = "sarvam-m"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = Field(None, le=4096)


@router.post("/api/llm/chat")
async def llm_chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
):
    """Proxy chat completion requests to Sarvam AI so the Flutter client
    never needs the API key."""

    payload = {
        "model": "sarvam-m",
        "messages": body.messages,
    }
    if body.temperature is not None:
        payload["temperature"] = body.temperature
    if body.max_tokens is not None:
        payload["max_tokens"] = body.max_tokens

    url = f"{settings.SARVAM_BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.SARVAM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers=headers, timeout=60.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            from fastapi.responses import JSONResponse

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
