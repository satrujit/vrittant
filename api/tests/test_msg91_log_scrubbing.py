"""Security: MSG91 service must NOT print/log secrets, OTPs, or full phone numbers.

Vuln (pre-fix): _widget_request did `print(f"... body={data}")` which dumped
MSG91 response bodies — including OTP codes on verifyOtp responses and any
echoed authkey/tokenAuth from request payloads — to Cloud Run stdout.
"""

import asyncio
import logging

import pytest
import respx
from httpx import Response

from app.services import msg91


@pytest.fixture(autouse=True)
def _set_msg91_keys(monkeypatch):
    """Inject fake credentials so the service has values to potentially leak."""
    monkeypatch.setattr(msg91.settings, "MSG91_AUTHKEY", "SECRET-AUTHKEY-12345")
    monkeypatch.setattr(msg91.settings, "MSG91_TOKEN_AUTH", "SECRET-TOKENAUTH-67890")
    monkeypatch.setattr(msg91.settings, "MSG91_WIDGET_ID", "widget-1")


@respx.mock
def test_send_otp_does_not_leak_secrets_to_logs(caplog, capsys):
    """MSG91 sometimes echoes identifier (the phone) in the response. Logging
    must redact phone + must never include authkey/tokenAuth."""
    caplog.set_level(logging.DEBUG)

    respx.post("https://api.msg91.com/api/v5/widget/sendOtp").mock(
        return_value=Response(
            200,
            json={
                "type": "success",
                "message": "req-123",
                "identifier": "919999999999",   # MSG91 echoes the mobile here
                "authkey": "SECRET-AUTHKEY-12345",  # paranoid: if it ever echoed
            },
        )
    )

    asyncio.run(msg91.send_otp("+919999999999"))

    captured = capsys.readouterr()
    log_text = caplog.text + captured.out + captured.err

    forbidden = [
        "SECRET-AUTHKEY-12345",
        "SECRET-TOKENAUTH-67890",
        "919999999999",
        "+919999999999",
    ]
    for needle in forbidden:
        assert needle not in log_text, (
            f"Sensitive value {needle!r} appeared in logs/stdout: {log_text!r}"
        )


@respx.mock
def test_verify_otp_does_not_leak_otp_to_logs(caplog, capsys):
    """On verifyOtp failures MSG91 echoes the submitted OTP back in the message.
    That must never reach logs."""
    caplog.set_level(logging.DEBUG)

    respx.post("https://api.msg91.com/api/v5/widget/verifyOtp").mock(
        return_value=Response(
            400,
            json={"type": "error", "message": "OTP 123456 is incorrect"},
        )
    )

    try:
        asyncio.run(msg91.verify_otp("+919999999999", "123456", req_id="r1"))
    except Exception:
        pass  # MSG91 error is expected — we only care about what got logged

    captured = capsys.readouterr()
    log_text = caplog.text + captured.out + captured.err

    assert "123456" not in log_text, f"OTP leaked into logs: {log_text!r}"
    assert "SECRET-AUTHKEY-12345" not in log_text
    assert "SECRET-TOKENAUTH-67890" not in log_text
    assert "919999999999" not in log_text
