"""
MSG91 OTP service — SendOTP API + Widget token verification.

- Mobile: backend calls MSG91 SendOTP API (send / verify / resend)
  using the DLT-registered template.
- Web: client-side widget, backend verifies access token via Widget API.
"""

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

OTP_BASE = "https://control.msg91.com/api/v5/otp"
WIDGET_BASE = "https://api.msg91.com/api/v5/widget"

# Suppress httpx's built-in request logging — it logs full URLs including
# query params, which would leak authkey, phone numbers, and OTP codes.
logging.getLogger("httpx").setLevel(logging.WARNING)


def _normalize_phone(phone: str) -> str:
    """Strip '+' prefix so +91XXXX → 91XXXX."""
    return phone.lstrip("+")


async def _otp_post(url: str, payload: dict) -> dict:
    """POST to MSG91 SendOTP API with authkey header."""
    headers = {
        "authkey": settings.MSG91_AUTHKEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, json=payload)

    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}

    endpoint = url.rsplit("/", 1)[-1]
    logger.info("MSG91 POST %s status=%d", endpoint, resp.status_code)
    return data


async def _otp_get(url: str, params: dict) -> dict:
    """GET from MSG91 SendOTP API with authkey header."""
    headers = {
        "authkey": settings.MSG91_AUTHKEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers, params=params)

    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}

    endpoint = url.rsplit("/", 1)[-1]
    logger.info("MSG91 GET %s status=%d", endpoint, resp.status_code)
    return data


# ── Widget token verification (web — unchanged) ──

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


# ── SendOTP API (mobile) ──

async def send_otp(phone: str) -> dict:
    """Send OTP via MSG91 SendOTP API with DLT template."""
    mobile = _normalize_phone(phone)

    data = await _otp_post(OTP_BASE, {
        "template_id": settings.MSG91_TEMPLATE_ID,
        "mobile": mobile,
        "otp_length": 6,
    })

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 send_otp failed: {data.get('message', data)}")

    data["reqId"] = data.get("request_id", "")
    return data


async def verify_otp(phone: str, otp: str, req_id: str = "") -> dict:
    """Verify OTP via MSG91 SendOTP API."""
    mobile = _normalize_phone(phone)

    data = await _otp_get(f"{OTP_BASE}/verify", params={
        "mobile": mobile,
        "otp": otp,
    })

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 verify_otp failed: {data.get('message', data)}")

    return data


async def resend_otp(phone: str, req_id: str = "") -> dict:
    """Resend OTP — call send_otp again.

    MSG91's /retry endpoint has a known issue rejecting valid authkeys.
    Re-sending via the main endpoint works identically.
    """
    return await send_otp(phone)
