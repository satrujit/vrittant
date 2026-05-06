"""Tests for handle_quoted_reply — adding content to an existing story
via reply-quote of our saved-confirmation message."""
import asyncio
from unittest.mock import AsyncMock, patch

from app.models.user import User
from app.models.organization import Organization
from app.models.story import Story
from app.models.whatsapp_buffer import WhatsAppThreadState


def _seed_user(db, lang="en", id_="u", phone="+919"):
    org = db.query(Organization).filter_by(id="o").first()
    if org is None:
        org = Organization(id="o", name="X", slug="x", default_language=lang)
        db.add(org)
    user = User(
        id=id_, phone=phone, name="N",
        organization="X", organization_id="o", user_type="reporter",
        is_active=True,
    )
    db.add(user); db.commit()
    db.refresh(user, ["org"])
    return user


def _quoted_text_payload(context_id: str, body: str) -> dict:
    return {
        "type": "text",
        "context": {"id": context_id},
        "text": {"body": body},
    }


def _run(coro):
    return asyncio.run(coro)


@patch("app.services.whatsapp.dispatcher.handle_forward", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_quoted_reply_with_no_matching_story_falls_through_to_forward(mock_send, mock_fwd, db):
    from app.services.whatsapp.dispatcher import handle_quoted_reply
    user = _seed_user(db)
    # No story has whatsapp_confirm_message_id == "wamid.UNKNOWN"
    payload = _quoted_text_payload("wamid.UNKNOWN", "Some new content for a fresh story body here today.")
    _run(handle_quoted_reply(db=db, sender_phone="+919", user=user, payload=payload))
    mock_fwd.assert_called_once()  # treated as a fresh forward


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_quoted_reply_to_other_reporters_story_rejected(mock_send, db):
    from app.services.whatsapp.dispatcher import handle_quoted_reply
    user = _seed_user(db, id_="u", phone="+919")
    # Other reporter's story
    other = User(
        id="u_other", phone="+92", name="O",
        organization="X", organization_id="o", user_type="reporter",
        is_active=True,
    )
    db.add(other); db.commit()
    s = Story(
        id="s_theirs", organization_id="o", reporter_id="u_other",
        seq_no=1, headline="theirs", paragraphs=[], status="submitted",
        source="whatsapp", whatsapp_confirm_message_id="wamid.OTHER",
    )
    db.add(s); db.commit()

    payload = _quoted_text_payload("wamid.OTHER", "Trying to add to someone else's story body here today.")
    _run(handle_quoted_reply(db=db, sender_phone="+919", user=user, payload=payload))
    body = mock_send.call_args.kwargs["body"]
    assert "another reporter" in body.lower() or "ସମ୍ପାଦନ" in body


@patch("app.services.whatsapp.dispatcher.handle_forward", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_quoted_reply_to_locked_story_replies_locked_then_falls_through(mock_send, mock_fwd, db):
    from app.services.whatsapp.dispatcher import handle_quoted_reply
    user = _seed_user(db)
    s = Story(
        id="s_locked", organization_id="o", reporter_id="u",
        seq_no=1, headline="locked", paragraphs=[], status="approved",  # locked
        source="whatsapp", whatsapp_confirm_message_id="wamid.LOCKED",
    )
    db.add(s); db.commit()

    payload = _quoted_text_payload("wamid.LOCKED", "Trying to add to a locked story body here today friends.")
    _run(handle_quoted_reply(db=db, sender_phone="+919", user=user, payload=payload))

    # User informed
    body = mock_send.call_args.kwargs["body"]
    assert "locked" in body.lower() or "ଲକ୍" in body
    # Then content went through as a fresh forward
    mock_fwd.assert_called_once()


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.ADDING")
def test_quoted_reply_opens_add_thread_and_processes_text(mock_edit, db):
    from app.services.whatsapp.dispatcher import handle_quoted_reply
    user = _seed_user(db)
    s = Story(
        id="s_mine", organization_id="o", reporter_id="u",
        seq_no=1, headline="mine", paragraphs=[], status="submitted",
        source="whatsapp", whatsapp_confirm_message_id="wamid.MINE",
    )
    db.add(s); db.commit()

    payload = _quoted_text_payload(
        "wamid.MINE",
        "Adding more details about the story body here today friends and editors "
        "with extra context about the bypoll outcome and what happened next really.",
    )
    _run(handle_quoted_reply(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts is not None
    assert ts.thread_kind == "add"
    assert ts.target_story_id == "s_mine"
    assert "Adding more details" in ts.pending_text_concat
    # Buttons sent (Save additions / Discard)
    mock_edit.assert_called_once()


@patch("app.services.whatsapp.dispatcher.outbound.edit_or_send_interactive",
       new_callable=AsyncMock, return_value="wamid.ADDING_M")
def test_quoted_reply_with_image_buffers_into_add_thread(mock_edit, db):
    from app.services.whatsapp.dispatcher import handle_quoted_reply
    from app.models.whatsapp_buffer import WhatsAppPendingMedia
    user = _seed_user(db)
    s = Story(
        id="s_mine", organization_id="o", reporter_id="u",
        seq_no=1, headline="mine", paragraphs=[], status="submitted",
        source="whatsapp", whatsapp_confirm_message_id="wamid.MINE",
    )
    db.add(s); db.commit()

    payload = {
        "type": "image",
        "context": {"id": "wamid.MINE"},
        "image": {"id": "m1", "url": "https://gupshup/m1"},
    }
    _run(handle_quoted_reply(db=db, sender_phone="+919", user=user, payload=payload))
    db.commit()

    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts is not None
    assert ts.thread_kind == "add"
    assert ts.pending_media_count == 1

    pm = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+919").first()
    assert pm is not None
    assert pm.gupshup_media_url == "https://gupshup/m1"
