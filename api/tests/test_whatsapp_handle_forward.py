"""Tests for the handle_forward dispatcher handler.

handle_forward owns the inbound side: buffering media, accumulating
text, editing the [Submit][Cancel] interactive message. It does NOT
create stories — Task 14's handle_button (submit_thread case) does that.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.models.user import User
from app.models.organization import Organization
from app.models.story import Story
from app.models.whatsapp_buffer import (
    WhatsAppPendingMedia, WhatsAppThreadState, WhatsAppContentDedup,
)


def _seed_user(db, lang="or", phone="+919"):
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


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive", new_callable=AsyncMock)
def test_unregistered_sender_gets_polite_decline(mock_edit, mock_send, db):
    from app.services.whatsapp.dispatcher import handle_forward
    payload = {"type": "text", "payload": {"text": "Twenty word message at least to clear the threshold for the test bypass."}}
    _run(handle_forward(db=db, sender_phone="+91999", user=None, payload=payload))
    db.commit()
    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body"]
    assert "registered" in body.lower() or "ପଞ୍ଜିକୃତ" in body
    # No thread, no story
    assert db.query(WhatsAppThreadState).count() == 0
    assert db.query(Story).count() == 0


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive", new_callable=AsyncMock)
def test_under_20_words_rejected_without_thread(mock_edit, mock_send, db):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db, lang="en")
    payload = {"type": "text", "payload": {"text": "too short and lazy"}}
    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()
    body = mock_send.call_args.kwargs["body"]
    assert "20+" in body or "20 शब्द" in body or "୨୦+" in body
    assert db.query(WhatsAppThreadState).count() == 0
    assert mock_edit.called is False


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.NEW1")
def test_text_forward_opens_thread_and_sends_buttons(mock_edit, mock_send, db):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db, lang="en")
    body = "Bypoll results announced today across the state. BJP won three seats and Congress won one in a closely fought contest."
    payload = {"type": "text", "payload": {"text": body}}

    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    # Thread created
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts is not None
    assert ts.pending_text_count == 1
    assert "Bypoll results" in ts.pending_text_concat
    assert ts.interactive_msg_id == "wamid.NEW1"

    # Interactive buttons sent (with Submit + Cancel)
    mock_edit.assert_called_once()
    buttons = mock_edit.call_args.kwargs["buttons"]
    assert buttons[0][0] == "submit_thread"
    assert buttons[1][0] == "cancel_thread"

    # No plain-text reply
    mock_send.assert_not_called()


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.NEW")
def test_image_forward_buffers_media_no_story(mock_edit, db):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db)
    payload = {"type": "image", "payload": {"url": "https://gupshup/m1"}}

    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    rows = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+919").all()
    assert len(rows) == 1
    assert rows[0].media_type == "image"
    assert rows[0].drained_at is None

    # Thread created with media count
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts.pending_media_count == 1
    assert ts.pending_text_count == 0

    # No story created
    assert db.query(Story).count() == 0


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.A")
def test_text_then_image_in_same_thread(mock_edit, db):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db)

    # Text first
    text_body = "Bypoll results announced today across the state. BJP won three seats with comfortable margins everywhere in a closely fought election held this week."
    _run(handle_forward(db=db, sender_phone="+919", user=user,
                         payload={"type": "text", "payload": {"text": text_body}}))
    db.commit()

    # Then image
    _run(handle_forward(db=db, sender_phone="+919", user=user,
                         payload={"type": "image", "payload": {"url": "https://gupshup/m1"}}))
    db.commit()

    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts.pending_text_count == 1
    assert ts.pending_media_count == 1
    # edit_or_send_interactive called twice (initial send + edit)
    assert mock_edit.call_count == 2


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.D")
def test_duplicate_text_silently_skipped(mock_edit, db):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db)
    text = "Bypoll results announced today across the state. BJP won three seats with margins in a closely fought election held this week across districts."
    payload = {"type": "text", "payload": {"text": text}}

    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()
    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    # Only one text entry counted
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts.pending_text_count == 1
    # Outbound called once for the first arrival; second was silent
    assert mock_edit.call_count == 1


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.X")
def test_forwarded_boilerplate_stripped(mock_edit, db):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db)
    raw = "> Forwarded from: Pradip\n> Original sender: A\nBypoll results announced today across the state with BJP winning three seats in a closely fought election held this week across all districts."
    _run(handle_forward(db=db, sender_phone="+919", user=user,
                         payload={"type": "text", "payload": {"text": raw}}))
    db.commit()
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    # Boilerplate must NOT be in the stored body
    assert "Forwarded from" not in ts.pending_text_concat
    assert "Bypoll results" in ts.pending_text_concat


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.E")
def test_idle_thread_force_closed_before_new_forward(mock_edit, db):
    """A reporter who returns after 60s+ with a fresh forward starts a
    NEW thread, not appending to the stale one."""
    from datetime import datetime, timedelta, timezone
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db)

    # Seed a stale thread with prior text and prior interactive_msg_id
    stale = WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=2,
        pending_text_concat="old story body",
        pending_media_count=0,
        last_message_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        interactive_msg_id="wamid.OLD",
    )
    db.add(stale); db.commit()

    text = "Fresh news arrived now across the state today with BJP winning three seats convincingly in a closely fought election held this week."
    _run(handle_forward(db=db, sender_phone="+919", user=user,
                         payload={"type": "text", "payload": {"text": text}}))
    db.commit()

    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts.pending_text_count == 1  # fresh start, NOT 3
    assert "old story body" not in ts.pending_text_concat
    assert "Fresh news" in ts.pending_text_concat
    # Old interactive_msg_id discarded; sent fresh (existing_msg_id=None on edit_or_send)
    call_kwargs = mock_edit.call_args.kwargs
    assert call_kwargs["existing_msg_id"] is None


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.F")
def test_audio_forward_buffers_without_transcription(mock_edit, db):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db)
    payload = {"type": "audio", "payload": {"url": "https://gupshup/a1"}}

    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    rows = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+919").all()
    assert len(rows) == 1
    assert rows[0].media_type == "audio"
    # Thread updated
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts.pending_media_count == 1


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.G")
def test_pdf_forward_buffers_as_document(mock_edit, db):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db)
    payload = {"type": "document", "payload": {"url": "https://gupshup/d1"}}

    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    rows = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+919").all()
    assert len(rows) == 1
    assert rows[0].media_type == "document"


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.H")
def test_first_forward_uses_thread_first_template(mock_edit, db):
    """Single-message thread uses 'thread.first' (no count) — body checked."""
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db, lang="en")
    text = "Bypoll results announced today across the state with BJP winning three seats convincingly today in a closely fought election held this week."
    _run(handle_forward(db=db, sender_phone="+919", user=user,
                         payload={"type": "text", "payload": {"text": text}}))
    body = mock_edit.call_args.kwargs["body"]
    assert "Got 1 message" in body


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.I")
def test_subsequent_forward_uses_thread_update_template(mock_edit, db):
    """Multi-message thread renders the 'thread.update' template with counts."""
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db, lang="en")
    text = "Bypoll results announced today across the state with BJP winning three seats convincingly in a closely fought election held this week across districts."
    _run(handle_forward(db=db, sender_phone="+919", user=user,
                         payload={"type": "text", "payload": {"text": text}}))
    _run(handle_forward(db=db, sender_phone="+919", user=user,
                         payload={"type": "image", "payload": {"url": "https://gupshup/x"}}))
    db.commit()
    body = mock_edit.call_args.kwargs["body"]
    assert "Got 2 messages" in body
    assert "1 text" in body
    assert "1 media" in body
