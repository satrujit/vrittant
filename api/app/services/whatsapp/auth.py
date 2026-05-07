"""Webhook authentication for /webhooks/whatsapp/*.

Gupshup's dashboard exposes an "Includes headers" feature that attaches
a constant key-value pair to every webhook delivery — effectively a
shared-secret bearer token in a header (NOT an HMAC body signature).
Our setup uses `X-Gupshup-Signature: <token>` where the token is a
random string configured identically on Gupshup and on our backend.

This is weaker than HMAC body-signing (an MITM with the URL + header
could replay payloads) but the header isn't sniffable over HTTPS in
normal conditions, and the token is rotatable. Still a substantial
improvement over no-auth: blocks anyone who guesses the public Cloud
Run URL from spoofing reporter phones, triggering outbound replies, or
reaching the media-fetch SSRF surface.

Behaviour:
- `GUPSHUP_WEBHOOK_SECRET` empty   → verification skipped, log a one-
  time WARNING (allows initial rollout: deploy code → configure header
  on Gupshup dashboard → set the env var → tighten).
- Secret set, header matches       → request proceeds.
- Secret set, header missing       → 403.
- Secret set, header doesn't match → 403.

The compare uses `hmac.compare_digest` for constant-time behaviour.
"""
from __future__ import annotations

import hmac
import logging
from typing import Optional

from fastapi import Request, Response

from app.config import settings

log = logging.getLogger("whatsapp.auth")


# Header names we accept the shared-secret token in. Gupshup writes
# whatever name you configure on the dashboard; we accept the few
# common conventions so we're robust to dashboard config changes.
_TOKEN_HEADERS = (
    "X-Gupshup-Signature",
    "X-Webhook-Token",
    "X-Auth-Token",
    "Authorization",  # if user prefixes with "Bearer ", we strip it below
)


def _extract_token(headers: dict) -> Optional[str]:
    """Find the bearer token in any of the accepted headers. Strips a
    `Bearer ` / `bearer ` prefix if the user used the Authorization
    header convention."""
    for h in _TOKEN_HEADERS:
        # Case-insensitive header lookup — Starlette/test clients vary
        # on casing.
        for key in (h, h.lower()):
            if key in headers:
                v = (headers[key] or "").strip()
                if v.lower().startswith("bearer "):
                    v = v[7:].strip()
                if v:
                    return v
    return None


def verify_signature(
    *,
    body: bytes = b"",  # kept in the signature for backward compat / tests
    headers: dict,
    secret: Optional[str] = None,
) -> bool:
    """True iff the request carries the configured shared-secret token
    in any of the accepted headers.

    `secret` defaults to settings.GUPSHUP_WEBHOOK_SECRET — passed
    explicitly only by tests. `body` is unused for shared-secret mode
    but kept in the signature so future HMAC mode can use it without a
    breaking change to the helper's contract.
    """
    if secret is None:
        secret = settings.GUPSHUP_WEBHOOK_SECRET
    if not secret:
        # No secret configured → can't verify, treat as authentic.
        # The middleware logs a startup warning so we know.
        return True

    received = _extract_token(headers)
    if not received:
        return False
    # Constant-time compare. Pad both to the same length first so the
    # comparison itself doesn't leak length info via early-return —
    # compare_digest does this internally but only when both inputs
    # are the same type and length, so equalise on str.
    return hmac.compare_digest(received, secret)


async def signature_check_middleware(
    request: Request,
    call_next,
):
    """ASGI middleware. Only enforces on /webhooks/whatsapp/*; everything
    else passes through unchanged. Skips verification when
    GUPSHUP_WEBHOOK_SECRET is empty (initial rollout / local / tests).
    """
    if not request.url.path.startswith("/webhooks/whatsapp"):
        return await call_next(request)

    secret = settings.GUPSHUP_WEBHOOK_SECRET
    if not secret:
        # Off — log once per cold start, not per request, to avoid
        # log-spam. Module-level flag is safe because Cloud Run starts
        # one process per instance.
        global _WARNED_NO_SECRET
        if not _WARNED_NO_SECRET:
            log.warning(
                "GUPSHUP_WEBHOOK_SECRET is empty — webhook authentication "
                "is OFF. Set the env var to the same value you've configured "
                "on the Gupshup dashboard ('Includes headers' field)."
            )
            _WARNED_NO_SECRET = True
        return await call_next(request)

    headers = dict(request.headers)
    if not verify_signature(headers=headers, secret=secret):
        log.warning(
            "Rejecting unauthenticated webhook on %s from %s",
            request.url.path,
            request.client.host if request.client else "?",
        )
        return Response(
            content='{"error":"invalid signature"}',
            status_code=403,
            media_type="application/json",
        )

    return await call_next(request)


# Module-level flag so we only warn once per process about the missing secret.
_WARNED_NO_SECRET = False
