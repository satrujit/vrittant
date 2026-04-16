"""
MSG91 OTP service — Widget API.
- Mobile: backend calls Widget API endpoints (sendOtp / verifyOtp / retryOtp).
- Web: client-side widget, backend verifies access token.

Cloud Run egress goes through Cloud NAT (static IP 34.93.149.224)
to avoid shared-IP blocking by MSG91.
"""

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

WIDGET_BASE = "https://api.msg91.com/api/v5/widget"


def _normalize_phone(phone: str) -> str:
    """Strip '+' prefix so +91XXXX → 91XXXX."""
    return phone.lstrip("+")


async def _widget_request(method: str, url: str, **kwargs) -> dict:
    """Make an authenticated request to MSG91 Widget API."""
    headers = {
        "authkey": settings.MSG91_AUTHKEY,
        "token": settings.MSG91_TOKEN_AUTH,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await getattr(client, method)(url, headers=headers, **kwargs)

    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}

    print(f"MSG91 {method.upper()} {url} status={resp.status_code} body={data}")
    return data


# ── Widget token verification (web) ──

async def verify_access_token(access_token: str) -> dict:
    """Verify access token from MSG91 OTP Widget (web flow)."""
    url = f"{WIDGET_BASE}/verifyAccessToken"
    data = await _widget_request("post", url, json={
        "authkey": settings.MSG91_AUTHKEY,
        "access-token": access_token,
    })

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 token verification failed: {data.get('message', data)}")

    return data


# ── Widget OTP endpoints (mobile — backend calls Widget API) ──

async def send_otp(phone: str) -> dict:
    """Send OTP via Widget API."""
    mobile = _normalize_phone(phone)
    url = f"{WIDGET_BASE}/sendOtp"

    data = await _widget_request("post", url, json={
        "widgetId": settings.MSG91_WIDGET_ID,
        "tokenAuth": settings.MSG91_TOKEN_AUTH,
        "identifier": mobile,
    })

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 send_otp failed: {data.get('message', data)}")

    req_id = ""
    if isinstance(data.get("data"), dict):
        req_id = data["data"].get("message", "")
    elif isinstance(data.get("message"), str):
        req_id = data["message"]
    data["reqId"] = req_id
    return data


async def verify_otp(phone: str, otp: str, req_id: str = "") -> dict:
    """Verify OTP via Widget API."""
    mobile = _normalize_phone(phone)
    url = f"{WIDGET_BASE}/verifyOtp"

    data = await _widget_request("post", url, json={
        "widgetId": settings.MSG91_WIDGET_ID,
        "tokenAuth": settings.MSG91_TOKEN_AUTH,
        "identifier": mobile,
        "otp": otp,
        "reqId": req_id,
    })

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 verify_otp failed: {data.get('message', data)}")

    return data


async def resend_otp(phone: str, req_id: str = "") -> dict:
    """Resend OTP via Widget API."""
    mobile = _normalize_phone(phone)
    url = f"{WIDGET_BASE}/retryOtp"

    data = await _widget_request("post", url, json={
        "widgetId": settings.MSG91_WIDGET_ID,
        "tokenAuth": settings.MSG91_TOKEN_AUTH,
        "identifier": mobile,
        "reqId": req_id,
    })

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 resend_otp failed: {data.get('message', data)}")

    return data
