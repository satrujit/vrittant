"""Tests for the WhatsApp dispatcher.

Each test patches all four handlers and asserts only the right one
was called for a given payload kind.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest


def _run(coro):
    return asyncio.run(coro)


@patch("app.services.whatsapp.dispatcher.handle_button", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_quoted_reply", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_forward", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_skip", new_callable=AsyncMock)
def test_dispatch_routes_button(skip, fwd, qr, btn):
    from app.services.whatsapp.dispatcher import dispatch
    payload = {
        "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "submit_thread"}},
    }
    _run(dispatch(db=None, sender_phone="+91", user=None, payload=payload))
    assert btn.called
    assert not (qr.called or fwd.called or skip.called)


@patch("app.services.whatsapp.dispatcher.handle_button", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_quoted_reply", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_forward", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_skip", new_callable=AsyncMock)
def test_dispatch_routes_quoted_reply(skip, fwd, qr, btn):
    from app.services.whatsapp.dispatcher import dispatch
    payload = {"type": "text", "context": {"id": "wamid.X"}, "text": {"body": "more"}}
    _run(dispatch(db=None, sender_phone="+91", user=None, payload=payload))
    assert qr.called
    assert not (btn.called or fwd.called or skip.called)


@patch("app.services.whatsapp.dispatcher.handle_button", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_quoted_reply", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_forward", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_skip", new_callable=AsyncMock)
def test_dispatch_routes_forward_text(skip, fwd, qr, btn):
    from app.services.whatsapp.dispatcher import dispatch
    payload = {"type": "text", "text": {"body": "Some news content."}}
    _run(dispatch(db=None, sender_phone="+91", user=None, payload=payload))
    assert fwd.called


@patch("app.services.whatsapp.dispatcher.handle_button", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_quoted_reply", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_forward", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_skip", new_callable=AsyncMock)
def test_dispatch_routes_sticker_to_skip(skip, fwd, qr, btn):
    from app.services.whatsapp.dispatcher import dispatch
    payload = {"type": "sticker"}
    _run(dispatch(db=None, sender_phone="+91", user=None, payload=payload))
    assert skip.called


@patch("app.services.whatsapp.dispatcher.handle_button", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_quoted_reply", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_forward", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.handle_skip", new_callable=AsyncMock)
def test_dispatch_routes_unknown_type_to_skip(skip, fwd, qr, btn):
    from app.services.whatsapp.dispatcher import dispatch
    payload = {"type": "video_note"}
    _run(dispatch(db=None, sender_phone="+91", user=None, payload=payload))
    assert skip.called
    # Verify the skip handler got the right kind
    from app.services.whatsapp.classifier import MessageKind
    assert skip.call_args.kwargs["kind"] == MessageKind.SKIP_OTHER


def test_resolve_user_for_phone_finds_existing(db):
    """The user-resolution helper finds an active reporter by phone."""
    from app.models.user import User
    from app.services.whatsapp.dispatcher import resolve_user_for_phone

    u = User(
        id="u1", phone="+919437115223", name="X",
        organization="O", organization_id="o1", user_type="reporter",
        is_active=True,
    )
    db.add(u); db.commit()
    found = resolve_user_for_phone(db, "+919437115223")
    assert found is not None
    assert found.id == "u1"


def test_resolve_user_for_phone_returns_none_for_unknown(db):
    from app.services.whatsapp.dispatcher import resolve_user_for_phone
    assert resolve_user_for_phone(db, "+919999999999") is None


def test_resolve_user_for_phone_skips_deactivated(db):
    """Deactivated reporters should NOT resolve — they're effectively
    not registered for new submissions."""
    from datetime import datetime, timezone
    from app.models.user import User
    from app.services.whatsapp.dispatcher import resolve_user_for_phone

    u = User(
        id="u1", phone="+919437115223", name="X",
        organization="O", organization_id="o1", user_type="reporter",
        is_active=False,
    )
    db.add(u); db.commit()
    assert resolve_user_for_phone(db, "+919437115223") is None
