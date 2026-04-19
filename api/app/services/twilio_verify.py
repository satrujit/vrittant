"""
Twilio Verify OTP service.

Used for mobile OTP send/verify. Twilio Verify is a managed service:
- We don't pick the message body — Twilio's pre-registered template is used
- We don't manage retries — Twilio handles per-phone rate limiting internally
- No DLT registration required (Twilio uses their own pre-approved sender)

Endpoints:
- POST /v2/Services/{SID}/Verifications      → start verification
- POST /v2/Services/{SID}/VerificationCheck  → verify code

Authentication: HTTP Basic with Account SID + Auth Token.
"""

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

VERIFY_BASE = "https://verify.twilio.com/v2/Services"


def _normalize_phone(phone: str) -> str:
    """Twilio expects E.164 format (e.g. +919876543210). Our DB stores '+91...'
    so most numbers already conform; just strip whitespace and ensure leading '+'."""
    p = (phone or "").strip()
    if not p:
        return p
    return p if p.startswith("+") else "+" + p


async def _twilio_request(method: str, path: str, data: dict) -> dict:
    """Authenticated form-encoded request to Twilio Verify API."""
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_VERIFY_SERVICE_SID):
        raise RuntimeError("Twilio Verify credentials not configured")

    url = f"{VERIFY_BASE}/{settings.TWILIO_VERIFY_SERVICE_SID}/{path}"
    auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await getattr(client, method)(url, data=data, auth=auth)

    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    # SECURITY: don't log response body — it may echo the OTP code on errors.
    logger.info("Twilio %s %s status=%d", method.upper(), path, resp.status_code)

    if resp.status_code >= 400:
        # Twilio returns {"code": 60200, "message": "Invalid parameter", ...}
        msg = body.get("message", f"HTTP {resp.status_code}") if isinstance(body, dict) else str(body)
        raise RuntimeError(f"Twilio {path} failed: {msg}")

    return body


# ── Public API ──

async def send_otp(phone: str) -> dict:
    """Start a verification — Twilio sends the OTP via SMS."""
    mobile = _normalize_phone(phone)
    body = await _twilio_request("post", "Verifications", {"To": mobile, "Channel": "sms"})
    # Surface a stable shape compatible with the existing route handler.
    # Twilio returns "sid" (verification SID); we expose it as reqId for parity
    # with the MSG91 contract, but mobile clients don't actually need to keep it
    # because Twilio tracks state by phone number.
    return {"reqId": body.get("sid", ""), "raw": body}


async def verify_otp(phone: str, otp: str, req_id: str = "") -> dict:
    """Check a code submitted by the user."""
    mobile = _normalize_phone(phone)
    body = await _twilio_request("post", "VerificationCheck", {"To": mobile, "Code": otp})
    # Twilio returns {"status": "approved" | "pending" | "canceled", ...}
    if body.get("status") != "approved":
        raise RuntimeError(f"Twilio verifyOtp not approved: status={body.get('status')}")
    return body


async def resend_otp(phone: str, req_id: str = "") -> dict:
    """Twilio Verify has no separate resend — calling Verifications again
    triggers a fresh send (Twilio rate-limits internally per phone)."""
    return await send_otp(phone)
