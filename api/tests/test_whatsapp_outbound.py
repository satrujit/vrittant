"""Tests for the Gupshup outbound API wrapper.

We mock httpx.AsyncClient at the module level. Each test verifies the
wrapper sends the right payload shape AND extracts the messageId from
the response.
"""
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.services.whatsapp import outbound


def _mock_httpx_response(status: int, json_body: dict):
    """Build a MagicMock that looks like an httpx Response."""
    r = MagicMock()
    r.status_code = status
    r.text = json.dumps(json_body)
    r.json = MagicMock(return_value=json_body)
    return r


def _mock_async_client(post_response):
    """Build a context-manager mock for httpx.AsyncClient(timeout=10)."""
    instance = MagicMock()
    instance.post = AsyncMock(return_value=post_response)
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    cls = MagicMock(return_value=instance)
    return cls, instance


# ── send_text ────────────────────────────────────────────────────


def test_send_text_returns_message_id_on_success():
    cls, instance = _mock_async_client(_mock_httpx_response(200, {"messageId": "wamid.X"}))
    with patch.object(outbound.httpx, "AsyncClient", cls):
        msg_id = asyncio.run(outbound.send_text(to="+91", body="hello"))
    assert msg_id == "wamid.X"
    # Inspect the call: should hit /msg endpoint with type=text
    args, kwargs = instance.post.call_args
    assert "/msg" in args[0]
    msg_payload = json.loads(kwargs["data"]["message"])
    assert msg_payload["type"] == "text"
    assert msg_payload["text"] == "hello"


def test_send_text_returns_none_on_http_error():
    cls, _ = _mock_async_client(_mock_httpx_response(401, {"error": "unauthorized"}))
    with patch.object(outbound.httpx, "AsyncClient", cls):
        msg_id = asyncio.run(outbound.send_text(to="+91", body="hi"))
    assert msg_id is None


# ── send_interactive_buttons ─────────────────────────────────────


def test_send_interactive_buttons_constructs_correct_payload():
    """Asserts the Gupshup `quick_reply` proprietary shape (NOT WhatsApp
    Cloud API's `type: "interactive"` shape)."""
    cls, instance = _mock_async_client(_mock_httpx_response(200, {"messageId": "wamid.Y"}))
    with patch.object(outbound.httpx, "AsyncClient", cls):
        msg_id = asyncio.run(outbound.send_interactive_buttons(
            to="+91",
            body="Got 1.",
            buttons=[("submit_thread", "Submit"), ("cancel_thread", "Cancel")],
        ))
    assert msg_id == "wamid.Y"
    msg_payload = json.loads(instance.post.call_args.kwargs["data"]["message"])
    assert msg_payload["type"] == "quick_reply"
    assert msg_payload["content"]["type"] == "text"
    assert msg_payload["content"]["text"] == "Got 1."
    options = msg_payload["options"]
    assert [(o["title"], o["postbackText"]) for o in options] == [
        ("Submit", "submit_thread"), ("Cancel", "cancel_thread"),
    ]


def test_send_interactive_buttons_truncates_labels_to_20_chars():
    """WhatsApp caps button labels at 20 characters (UI limit)."""
    cls, instance = _mock_async_client(_mock_httpx_response(200, {"messageId": "x"}))
    with patch.object(outbound.httpx, "AsyncClient", cls):
        asyncio.run(outbound.send_interactive_buttons(
            to="+91", body="x",
            buttons=[("id", "A" * 50)],
        ))
    msg_payload = json.loads(instance.post.call_args.kwargs["data"]["message"])
    assert len(msg_payload["options"][0]["title"]) == 20


# ── send_interactive_list ────────────────────────────────────────


def test_send_interactive_list_constructs_correct_payload():
    """Asserts Gupshup's `list` proprietary shape."""
    cls, instance = _mock_async_client(_mock_httpx_response(200, {"messageId": "wamid.L"}))
    with patch.object(outbound.httpx, "AsyncClient", cls):
        msg_id = asyncio.run(outbound.send_interactive_list(
            to="+91",
            body="Pick one",
            button_label="Open menu",
            sections=[
                ("View", [
                    ("today", "My stories today", "Filed in last 24h"),
                    ("help", "Help", None),
                ]),
            ],
        ))
    assert msg_id == "wamid.L"
    msg_payload = json.loads(instance.post.call_args.kwargs["data"]["message"])
    assert msg_payload["type"] == "list"
    assert msg_payload["body"] == "Pick one"
    assert msg_payload["globalButtons"][0]["title"] == "Open menu"
    options = msg_payload["items"][0]["options"]
    assert options[0]["postbackText"] == "today"
    assert options[0]["description"] == "Filed in last 24h"
    assert "description" not in options[1]


# ── edit_or_send_interactive ─────────────────────────────────────


def test_edit_returns_existing_id_when_edit_succeeds():
    """Successful edit reuses the same messageId."""
    cls, _ = _mock_async_client(_mock_httpx_response(200, {"status": "edited"}))
    with patch.object(outbound.httpx, "AsyncClient", cls):
        msg_id = asyncio.run(outbound.edit_or_send_interactive(
            to="+91", existing_msg_id="wamid.OLD",
            body="updated",
            buttons=[("submit", "S"), ("cancel", "C")],
        ))
    assert msg_id == "wamid.OLD"


def test_edit_falls_back_to_new_send_on_http_error():
    """When edit returns non-200, send a fresh interactive."""
    instance = MagicMock()
    # First post (edit) → 400; second post (new send) → 200
    instance.post = AsyncMock(side_effect=[
        _mock_httpx_response(400, {"error": "edit window expired"}),
        _mock_httpx_response(200, {"messageId": "wamid.NEW"}),
    ])
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    cls = MagicMock(return_value=instance)

    with patch.object(outbound.httpx, "AsyncClient", cls):
        msg_id = asyncio.run(outbound.edit_or_send_interactive(
            to="+91", existing_msg_id="wamid.OLD",
            body="updated",
            buttons=[("submit", "S"), ("cancel", "C")],
        ))
    assert msg_id == "wamid.NEW"
    # Two HTTP calls were made
    assert instance.post.call_count == 2


def test_edit_falls_back_to_new_send_when_existing_msg_id_is_none():
    """If we have no prior msg_id, just send fresh — no edit attempt."""
    cls, instance = _mock_async_client(_mock_httpx_response(200, {"messageId": "wamid.NEW"}))
    with patch.object(outbound.httpx, "AsyncClient", cls):
        msg_id = asyncio.run(outbound.edit_or_send_interactive(
            to="+91", existing_msg_id=None,
            body="first time",
            buttons=[("submit", "S"), ("cancel", "C")],
        ))
    assert msg_id == "wamid.NEW"
    # Exactly one call (no edit attempt)
    assert instance.post.call_count == 1


def test_edit_falls_back_to_new_send_when_edit_raises():
    """Network exception during edit -> fall through to fresh send."""
    instance = MagicMock()
    instance.post = AsyncMock(side_effect=[
        Exception("connection reset"),
        _mock_httpx_response(200, {"messageId": "wamid.NEW2"}),
    ])
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    cls = MagicMock(return_value=instance)

    with patch.object(outbound.httpx, "AsyncClient", cls):
        msg_id = asyncio.run(outbound.edit_or_send_interactive(
            to="+91", existing_msg_id="wamid.OLD",
            body="x",
            buttons=[("a", "A"), ("b", "B")],
        ))
    assert msg_id == "wamid.NEW2"


# ── Phone normalisation ──────────────────────────────────────────


def test_to_phone_strips_plus_prefix():
    """Gupshup expects destinations without leading +."""
    cls, instance = _mock_async_client(_mock_httpx_response(200, {"messageId": "x"}))
    with patch.object(outbound.httpx, "AsyncClient", cls):
        asyncio.run(outbound.send_text(to="+919437115223", body="hi"))
    assert instance.post.call_args.kwargs["data"]["destination"] == "919437115223"
