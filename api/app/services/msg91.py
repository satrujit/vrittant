"""
MSG91 SendOTP service.

Send / verify / resend OTP via MSG91's SendOTP API.
Authkey placement varies by endpoint (MSG91 quirk):
  - send:   query param
  - verify: header
  - resend: query param
"""

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# Suppress httpx request logging — it logs full URLs which would
# leak authkey and phone numbers.
logging.getLogger("httpx").setLevel(logging.WARNING)

OTP_BASE = "https://control.msg91.com/api/v5/otp"


def _normalize_phone(phone: str) -> str:
    """Ensure phone has '+' prefix: +91XXXX."""
    phone = phone.strip()
    if not phone.startswith("+"):
        phone = "+" + phone
    return phone


async def send_otp(phone: str) -> dict:
    """Send OTP via MSG91 SendOTP API."""
    mobile = _normalize_phone(phone)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            OTP_BASE,
            params={
                "authkey": settings.MSG91_AUTHKEY,
                "template_id": settings.MSG91_TEMPLATE_ID,
                "mobile": mobile,
                "otp_length": "6",
            },
            headers={"Content-Type": "application/json"},
            json={},
        )

    data = _parse_response(resp)
    logger.info("MSG91 send_otp status=%d", resp.status_code)

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 send_otp failed: {data.get('message', data)}")

    data["reqId"] = data.get("request_id", "")
    return data


async def verify_otp(phone: str, otp: str, req_id: str = "") -> dict:
    """Verify OTP via MSG91 SendOTP API."""
    mobile = _normalize_phone(phone)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{OTP_BASE}/verify",
            params={"otp": otp, "mobile": mobile},
            headers={"authkey": settings.MSG91_AUTHKEY},
        )

    data = _parse_response(resp)
    logger.info("MSG91 verify_otp status=%d", resp.status_code)

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 verify_otp failed: {data.get('message', data)}")

    return data


async def resend_otp(phone: str, req_id: str = "") -> dict:
    """Resend OTP via MSG91 SendOTP API."""
    mobile = _normalize_phone(phone)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{OTP_BASE}/retry",
            params={
                "authkey": settings.MSG91_AUTHKEY,
                "mobile": mobile,
                "retrytype": "text",
            },
        )

    data = _parse_response(resp)
    logger.info("MSG91 resend_otp status=%d", resp.status_code)

    if data.get("type") == "error":
        raise RuntimeError(f"MSG91 resend_otp failed: {data.get('message', data)}")

    data["reqId"] = data.get("request_id", "")
    return data


def _parse_response(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}
