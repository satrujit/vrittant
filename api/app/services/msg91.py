"""
MSG91 OTP service — Direct OTP API + Widget token verification.

- Mobile: backend calls the MSG91 OTP API (send / verify / resend)
  using the DLT-registered SMS template.
- Web: client-side widget, backend verifies access token via Widget API.

The OTP API is separate from the Widget API. The OTP API uses
template_id (DLT-approved) and authkey only — no widget/token needed.
"""

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

OTP_BASE = "https://control.msg91.com/api/v5/otp"
WIDGET_BASE = "https://api.msg91.com/api/v5/widget"


def _normalize_phone(phone: str) -> str:
    """Strip '+' prefix so +91XXXX → 91XXXX."""
    return phone.lstrip("+")


async def _otp_request(method: str, url: str, **kwargs) -> dict:
    """Make an authenticated request to MSG91 OTP API."""
    headers = {
        "authkey": settings.MSG91_AUTHKEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await getattr(client, method)(url, headers=headers, **kwargs)

    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}

    endpoint = url.rsplit("/", 1)[-1]
    logger.info("MSG91 %s %s status=%d", method.upper(), endpoint, resp.status_code)
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


# ── Direct OTP API (mobile) ──

async def send_otp(phone: str) -> dict:
    """Send OTP via MSG91 OTP API with DLT template."""
    mobile = _normalize_phone(phone)

    data = await _otp_request("get", OTP_BASE, params={
        "authkey": settings.MSG91_AUTHKEY,
        "template_id": settings.MSG91_TEMPLATE_ID,
        "mobile": mobile,
    })

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 send_otp failed: {data.get('message', data)}")

    data["reqId"] = data.get("request_id", "")
    return data


async def verify_otp(phone: str, otp: str, req_id: str = "") -> dict:
    """Verify OTP via MSG91 OTP API."""
    mobile = _normalize_phone(phone)

    data = await _otp_request("get", f"{OTP_BASE}/verify", params={
        "authkey": settings.MSG91_AUTHKEY,
        "mobile": mobile,
        "otp": otp,
    })

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 verify_otp failed: {data.get('message', data)}")

    return data


async def resend_otp(phone: str, req_id: str = "") -> dict:
    """Resend OTP via MSG91 OTP API."""
    mobile = _normalize_phone(phone)

    data = await _otp_request("get", f"{OTP_BASE}/retry", params={
        "authkey": settings.MSG91_AUTHKEY,
        "mobile": mobile,
        "retrytype": "text",
    })

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 resend_otp failed: {data.get('message', data)}")

    data["reqId"] = data.get("request_id", "")
    return data
