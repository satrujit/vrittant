"""Tests for the background prompt_sender_loop.

The loop polls the DB for threads where last_message_at has settled
(older than SETTLE_SECONDS) and sends one consolidated [Submit][Cancel]
prompt per thread.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.user import User
from app.models.organization import Organization
from app.models.whatsapp_buffer import WhatsAppThreadState


def _seed_user(db, lang="en", phone="+919"):
    org = Organization(id="o", name="X", slug="x", default_language=lang)
    user = User(
        id="u", phone=phone, name="N",
        organization="X", organization_id="o", user_type="reporter",
        is_active=True,
    )
    db.add_all([org, user]); db.commit()
    db.refresh(user, ["org"])
    return user


def _run(coro):
    return asyncio.run(coro)


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.PROMPT1")
def test_settled_thread_gets_prompt(mock_edit, db):
    """A thread whose last_message_at is older than SETTLE_SECONDS
    should receive a [Submit][Cancel] prompt."""
    from app.services.whatsapp.dispatcher import _send_prompt_for_thread
    user = _seed_user(db)
    ts = WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=1,
        pending_media_count=2,
        last_message_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    db.add(ts); db.commit()
    db.refresh(ts)

    _run(_send_prompt_for_thread(ts, db))
    db.commit()

    mock_edit.assert_called_once()
    kwargs = mock_edit.call_args.kwargs
    assert kwargs["buttons"][0][0] == "submit_thread"
    assert kwargs["buttons"][1][0] == "cancel_thread"
    # interactive_msg_id set
    assert ts.interactive_msg_id == "wamid.PROMPT1"
    # prompt_sent_at set
    assert ts.prompt_sent_at is not None


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.PROMPT2")
def test_single_message_uses_thread_first_template(mock_edit, db):
    from app.services.whatsapp.dispatcher import _send_prompt_for_thread
    user = _seed_user(db)
    ts = WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=1,
        pending_media_count=0,
        last_message_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    db.add(ts); db.commit()
    db.refresh(ts)

    _run(_send_prompt_for_thread(ts, db))

    body = mock_edit.call_args.kwargs["body"]
    assert "Got 1 message" in body


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.PROMPT3")
def test_multi_message_uses_thread_update_template(mock_edit, db):
    from app.services.whatsapp.dispatcher import _send_prompt_for_thread
    user = _seed_user(db)
    ts = WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=1,
        pending_media_count=3,
        last_message_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    db.add(ts); db.commit()
    db.refresh(ts)

    _run(_send_prompt_for_thread(ts, db))

    body = mock_edit.call_args.kwargs["body"]
    assert "Got 4 messages" in body
    assert "1 text" in body
    assert "3 media" in body


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.PROMPT4")
def test_zero_count_thread_not_prompted(mock_edit, db):
    """Empty threads (e.g. after cancel) should NOT get a prompt."""
    from app.services.whatsapp.dispatcher import _send_prompt_for_thread
    ts = WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=0,
        pending_media_count=0,
        last_message_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    db.add(ts); db.commit()
    db.refresh(ts)

    _run(_send_prompt_for_thread(ts, db))

    mock_edit.assert_not_called()
