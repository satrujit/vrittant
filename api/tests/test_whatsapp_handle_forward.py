"""Tests for the handle_forward dispatcher handler.

handle_forward owns the inbound side: buffering media, accumulating
text, committing to DB, then returning immediately. Prompt delivery
is handled by the background prompt_sender_loop (tested separately
in test_whatsapp_prompt_loop.py).
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
       new_callable=AsyncMock, return_value="wamid.ADD1")
def test_under_20_words_accepted_in_add_mode(mock_edit, mock_send, db):
    """Add-mode appends to an existing story; the 20-word floor is for
    first submissions. A short follow-up like 'Police arrived at 9 PM'
    is legitimate and must NOT be rejected."""
    from app.services.whatsapp.dispatcher import handle_forward
    from app.services.whatsapp import thread_state
    user = _seed_user(db, lang="en")

    thread_state.open_or_get(
        db, sender_phone="+919",
        thread_kind="add", target_story_id="some-existing-story",
    )
    db.commit()

    short = "Police arrived at the scene around 9 PM."
    payload = {"type": "text", "payload": {"text": short}}
    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    # No "20+" rejection
    if mock_send.called:
        body = mock_send.call_args.kwargs.get("body", "")
        assert "20+" not in body and "୨୦+" not in body and "20 शब्द" not in body
    # Thread state still in add-mode, text count incremented
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts is not None
    assert ts.thread_kind == "add"
    assert (ts.pending_text_count or 0) >= 1
    # Prompt is NOT sent inline — the background loop handles it.
    # We only verify the data was buffered correctly.


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.NEW1")
def test_text_forward_opens_thread_and_buffers(mock_edit, mock_send, db):
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db, lang="en")
    body = "Bypoll results announced today across the state. BJP won three seats and Congress won one in a closely fought contest."
    payload = {"type": "text", "payload": {"text": body}}

    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    # Thread created with correct state
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts is not None
    assert ts.pending_text_count == 1
    assert "Bypoll results" in ts.pending_text_concat
    # Prompt NOT sent inline (no interactive call)
    mock_edit.assert_not_called()
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


@patch("app.services.whatsapp.dispatcher.outbound.send_text",
       new_callable=AsyncMock, return_value=None)
@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.G")
def test_pdf_forward_is_rejected_with_explainer(mock_edit, mock_send_text, db):
    """PDFs / DOCs are not supported on the WhatsApp self-service path."""
    from app.services.whatsapp.dispatcher import handle_forward
    user = _seed_user(db, lang="en")
    payload = {"type": "document", "payload": {"url": "https://gupshup/d1"}}

    _run(handle_forward(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    # Buffer not touched
    rows = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+919").all()
    assert rows == []
    # Thread state not touched (no count bump)
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts is None
    # User received the polite explainer
    assert mock_send_text.await_count == 1
    sent_body = mock_send_text.await_args.kwargs["body"]
    assert "PDF" in sent_body or "Files" in sent_body
    assert mock_edit.await_count == 0
