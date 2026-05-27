"""MSG91 SendOTP service — unit tests."""

import asyncio
import logging

import pytest
import respx
from httpx import Response

from app.services import msg91


@pytest.fixture(autouse=True)
def _set_msg91_keys(monkeypatch):
    monkeypatch.setattr(msg91.settings, "MSG91_AUTHKEY", "test-authkey")
    monkeypatch.setattr(msg91.settings, "MSG91_TEMPLATE_ID", "test-template")


@respx.mock
def test_send_otp_success():
    respx.post("https://control.msg91.com/api/v5/otp").mock(
        return_value=Response(200, json={"type": "success", "request_id": "req-123"})
    )
    result = asyncio.run(msg91.send_otp("+919999999999"))
    assert result["type"] == "success"
    assert result["reqId"] == "req-123"


@respx.mock
def test_send_otp_error_raises():
    respx.post("https://control.msg91.com/api/v5/otp").mock(
        return_value=Response(200, json={"type": "error", "message": "Invalid template"})
    )
    with pytest.raises(RuntimeError, match="send_otp failed"):
        asyncio.run(msg91.send_otp("+919999999999"))


@respx.mock
def test_verify_otp_success():
    respx.get("https://control.msg91.com/api/v5/otp/verify").mock(
        return_value=Response(200, json={"type": "success", "message": "OTP verified"})
    )
    result = asyncio.run(msg91.verify_otp("+919999999999", "123456"))
    assert result["type"] == "success"


@respx.mock
def test_verify_otp_error_raises():
    respx.get("https://control.msg91.com/api/v5/otp/verify").mock(
        return_value=Response(200, json={"type": "error", "message": "OTP expired"})
    )
    with pytest.raises(RuntimeError, match="verify_otp failed"):
        asyncio.run(msg91.verify_otp("+919999999999", "000000"))


@respx.mock
def test_resend_otp_success():
    respx.get("https://control.msg91.com/api/v5/otp/retry").mock(
        return_value=Response(200, json={"type": "success", "request_id": "req-456"})
    )
    result = asyncio.run(msg91.resend_otp("+919999999999"))
    assert result["type"] == "success"
    assert result["reqId"] == "req-456"


@respx.mock
def test_no_secrets_in_logs(caplog, capsys):
    """Authkey and phone must not appear in logs."""
    caplog.set_level(logging.DEBUG)

    respx.post("https://control.msg91.com/api/v5/otp").mock(
        return_value=Response(200, json={"type": "success", "request_id": "req-1"})
    )
    asyncio.run(msg91.send_otp("+919999999999"))

    captured = capsys.readouterr()
    log_text = caplog.text + captured.out + captured.err

    assert "test-authkey" not in log_text
    assert "919999999999" not in log_text


def test_normalize_phone_adds_plus():
    assert msg91._normalize_phone("919999999999") == "+919999999999"
    assert msg91._normalize_phone("+919999999999") == "+919999999999"
