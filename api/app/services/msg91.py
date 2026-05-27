"""
MSG91 — Widget token verification only.

Web login uses the MSG91 OTP Widget (client-side JS). The backend
verifies the resulting access token via this module.

Mobile OTP is handled by Twilio Verify (see twilio_verify.py).
"""

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

WIDGET_BASE = "https://api.msg91.com/api/v5/widget"


async def verify_access_token(access_token: str) -> dict:
    """Verify access token from MSG91 OTP Widget (web flow)."""
    headers = {
        "authkey": settings.MSG91_AUTHKEY,
        "token": settings.MSG91_TOKEN_AUTH,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{WIDGET_BASE}/verifyAccessToken", headers=headers, json={
            "authkey": settings.MSG91_AUTHKEY,
            "access-token": access_token,
        })
    data = resp.json()

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 token verification failed: {data.get('message', data)}")

    return data
