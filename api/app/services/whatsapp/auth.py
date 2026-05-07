"""Webhook signature verification for /webhooks/whatsapp/*.

Without this, anyone with the public Cloud Run URL can POST a payload
claiming to be from any reporter phone number — they can submit fake
stories, mutate open drafts, trigger outbound replies to arbitrary
numbers, and reach the media-fetch SSRF surface.

Gupshup signs every webhook with HMAC-SHA256 of the raw request body
using a shared secret you configure in their dashboard. The signature
is sent in the `X-Gupshup-Signature` header (some Gupshup tiers use
`X-Hub-Signature-256`; we accept either).

Behaviour:
- `GUPSHUP_WEBHOOK_SECRET` empty   → verification skipped, log a WARNING
  (allows initial rollout: deploy code → configure secret on Gupshup
  dashboard → set the env var → tighten).
- Secret set, valid signature      → request proceeds.
- Secret set, missing signature    → 403.
- Secret set, invalid signature    → 403.

The signature comparison uses `hmac.compare_digest` for constant-time
behaviour to prevent timing attacks on the secret.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

from fastapi import Request, Response

from app.config import settings

log = logging.getLogger("whatsapp.auth")


# Headers we accept the signature in, in priority order. Different Gupshup
# tiers / WhatsApp Cloud API integrations use different header names; we
# accept any of these to keep the integration robust to dashboard config
# changes.
_SIGNATURE_HEADERS = (
    "X-Gupshup-Signature",
    "X-Hub-Signature-256",
    "X-Hub-Signature",  # legacy SHA-1, accepted but not recommended
)


def _normalise_signature(raw: str) -> str:
    """Strip any algorithm prefix Gupshup/WhatsApp may include
    ('sha256=...', 'sha1=...') and lowercase the hex.
    """
    raw = (raw or "").strip()
    if "=" in raw:
        raw = raw.split("=", 1)[1]
    return raw.lower()


def _expected_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(
    *,
    body: bytes,
    headers: dict,
    secret: Optional[str] = None,
) -> bool:
    """Pure-functional signature check.

    `secret` defaults to settings.GUPSHUP_WEBHOOK_SECRET — passed
    explicitly only by tests.
    """
    if secret is None:
        secret = settings.GUPSHUP_WEBHOOK_SECRET
    if not secret:
        # No secret configured → can't verify, treat as authentic.
        # Caller is responsible for logging / alerting on this state.
        return True

    # Pull the signature from whichever header is present.
    sig_header = None
    for h in _SIGNATURE_HEADERS:
        if h in headers:
            sig_header = headers[h]
            break
        # Headers may be lowercase in some test harnesses
        lower = h.lower()
        if lower in headers:
            sig_header = headers[lower]
            break
    if not sig_header:
        return False

    expected = _expected_signature(secret, body)
    received = _normalise_signature(sig_header)
    return hmac.compare_digest(expected, received)


async def signature_check_middleware(
    request: Request,
    call_next,
):
    """ASGI middleware. Only enforces on /webhooks/whatsapp/*; everything
    else passes through unchanged. Skips verification when
    GUPSHUP_WEBHOOK_SECRET is empty (initial rollout / local / tests).

    Reads the raw request body once, then re-injects it into the request
    so downstream handlers can still parse it. (Starlette caches the
    body on the first read; the route handler's await request.json()
    sees the cached bytes.)
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
                "GUPSHUP_WEBHOOK_SECRET is empty — webhook signature "
                "verification is OFF. Set the env var once you've "
                "configured the matching secret on the Gupshup dashboard."
            )
            _WARNED_NO_SECRET = True
        return await call_next(request)

    body = await request.body()
    headers = dict(request.headers)
    if not verify_signature(body=body, headers=headers, secret=secret):
        log.warning(
            "Rejecting unsigned/invalid-signature webhook on %s from %s",
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
