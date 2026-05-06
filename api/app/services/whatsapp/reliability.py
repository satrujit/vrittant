"""Transient-error retry middleware for webhook routes.

A Cloud SQL connection can die mid-query (network blip, idle reaping,
maintenance failover). Without this middleware, FastAPI raises an
OperationalError, Cloud Run logs a 503, and Gupshup gives up after a
handful of retries — losing the inbound forward.

Strategy: catch transient SQLAlchemy/psycopg2 errors once, invalidate
the engine pool so subsequent connections come fresh, sleep 50ms,
replay the request. If the retry also fails we return 503 (Gupshup
will still retry naturally; at least we tried once at the application
layer).

Logical errors (IntegrityError, etc.) are never retried — a retry can
never resolve them.

Scoped to /webhooks/whatsapp/* in main.py; not a global middleware.
Webhooks are idempotent at the Gupshup boundary (whatsapp_inbound_dedup
keys on message_id) so a same-request replay is safe. Random user-
facing routes are NOT idempotent and are not wrapped.

Implementation note: Starlette's BaseHTTPMiddleware exposes a
``call_next`` callable that can only be invoked once per request (its
internal stream is closed on the first call). To implement a true
retry we capture the request body, attempt the first ``call_next``,
and on a transient failure dispatch the underlying ASGI app a second
time directly with a freshly buffered receive channel. The replayed
response is captured into a Response object and returned to the
client.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from fastapi import Request, Response
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

log = logging.getLogger("whatsapp.reliability")


# Substrings observed in transient connection-death errors. Matched against
# the lower-cased error message. Lengthening this list is fine; anything
# false-positive just causes one extra retry.
_TRANSIENT_HINTS = (
    "server closed",
    "connection reset",
    "ssl syscall error",
    "no message from the libpq",
    "could not connect to server",
    "connection refused",
    "pgres_tuples_ok",
    "terminating connection due to administrator command",
)


def is_transient_db_error(exc: BaseException) -> bool:
    """True for connection-death style errors that warrant a retry.

    False for logical errors (unique violation, FK violation, etc.) — those
    a retry can never fix and replaying would just double-bill any side
    effects upstream of the failure point.
    """
    if isinstance(exc, IntegrityError):
        return False
    if not isinstance(exc, (OperationalError, DBAPIError)):
        return False
    msg = str(exc).lower()
    return any(h in msg for h in _TRANSIENT_HINTS)


async def _replay_via_asgi(request: Request) -> Response:
    """Directly invoke the ASGI app a second time, returning a buffered Response.

    Used when a transient DB error fires on the first ``call_next`` — we can't
    re-invoke ``call_next`` (its stream is closed) so we dispatch the underlying
    ASGI app ourselves with a fresh receive channel.
    """
    body = await request.body()
    sent_event = {"type": "http.request", "body": body, "more_body": False}
    sent_once = {"done": False}

    async def receive() -> dict:
        if not sent_once["done"]:
            sent_once["done"] = True
            return sent_event
        # After the request body is delivered, block until cancelled.
        # In practice the app finishes before re-reading.
        return {"type": "http.disconnect"}

    status_code = 500
    headers: list[tuple[bytes, bytes]] = []
    body_chunks: list[bytes] = []

    async def send(message: dict[str, Any]) -> None:
        nonlocal status_code, headers
        if message["type"] == "http.response.start":
            status_code = message["status"]
            headers = list(message.get("headers") or [])
        elif message["type"] == "http.response.body":
            chunk = message.get("body", b"")
            if chunk:
                body_chunks.append(chunk)

    await request.app(request.scope, receive, send)

    response = Response(content=b"".join(body_chunks), status_code=status_code)
    # Replace default headers with the original response's so content-type etc. survive.
    response.raw_headers = headers
    return response


async def retry_on_transient_db_errors(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    try:
        return await call_next(request)
    except (OperationalError, DBAPIError) as exc:
        if not is_transient_db_error(exc):
            raise
        log.warning(
            "transient DB error on %s %s — invalidating pool + retrying once: %r",
            request.method, request.url.path, exc,
        )
        # Discard pooled connections; next checkout opens a fresh socket.
        try:
            from app.database import engine
            engine.dispose(close=False)
        except Exception:  # pragma: no cover — defensive
            log.exception("failed to dispose engine before retry")
        await asyncio.sleep(0.05)
        try:
            return await _replay_via_asgi(request)
        except Exception as exc2:
            log.error(
                "retry also failed on %s %s: %r",
                request.method, request.url.path, exc2,
            )
            return Response(
                content='{"error":"transient db error"}',
                status_code=503,
                media_type="application/json",
            )
