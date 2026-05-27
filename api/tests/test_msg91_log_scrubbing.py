"""Security: MSG91 widget verify must NOT leak secrets to logs."""

import asyncio
import logging

import pytest
import respx
from httpx import Response

from app.services import msg91


@pytest.fixture(autouse=True)
def _set_msg91_keys(monkeypatch):
    monkeypatch.setattr(msg91.settings, "MSG91_AUTHKEY", "SECRET-AUTHKEY-12345")
    monkeypatch.setattr(msg91.settings, "MSG91_TOKEN_AUTH", "SECRET-TOKENAUTH-67890")
    monkeypatch.setattr(msg91.settings, "MSG91_WIDGET_ID", "widget-1")


@respx.mock
def test_verify_access_token_does_not_leak_secrets(caplog, capsys):
    """verify_access_token must not log authkey or tokenAuth."""
    caplog.set_level(logging.DEBUG)

    respx.post("https://api.msg91.com/api/v5/widget/verifyAccessToken").mock(
        return_value=Response(
            200,
            json={"type": "success", "message": "verified"},
        )
    )

    asyncio.run(msg91.verify_access_token("test-access-token"))

    captured = capsys.readouterr()
    log_text = caplog.text + captured.out + captured.err

    assert "SECRET-AUTHKEY-12345" not in log_text
    assert "SECRET-TOKENAUTH-67890" not in log_text
