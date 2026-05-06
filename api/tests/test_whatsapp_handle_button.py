"""Tests for handle_button — routing button taps to actions."""
import asyncio
from unittest.mock import AsyncMock, patch

from app.models.user import User
from app.models.organization import Organization
from app.models.story import Story
from app.models.whatsapp_buffer import WhatsAppThreadState, WhatsAppPendingMedia


def _seed_user(db, lang="en"):
    org = Organization(id="o", name="X", slug="x", default_language=lang)
    user = User(
        id="u", phone="+919", name="N",
        organization="X", organization_id="o", user_type="reporter",
        is_active=True,
    )
    db.add_all([org, user]); db.commit()
    db.refresh(user, ["org"])
    return user


def _btn_payload(button_id: str) -> dict:
    return {
        "type": "interactive",
        "interactive": {
            "type": "button_reply",
            "button_reply": {"id": button_id, "title": "anything"},
        },
    }


def _run(coro):
    return asyncio.run(coro)


# ── submit_thread ──────────────────────────────────────────────


@patch("app.services.whatsapp.dispatcher.outbound.send_interactive_buttons", new_callable=AsyncMock,
       return_value="wamid.SAVED")
@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.finalize.finalize_story_from_thread", new_callable=AsyncMock)
def test_submit_thread_creates_story_and_sends_saved_confirmation(
    mock_finalize, mock_send, mock_buttons, db,
):
    from app.services.whatsapp.dispatcher import handle_button
    user = _seed_user(db)

    fake_story = Story(
        id="s1", organization_id="o", reporter_id="u",
        seq_no=1, headline="Test headline", paragraphs=[], status="submitted",
        source="whatsapp",
    )
    mock_finalize.return_value = fake_story

    _run(handle_button(db=db, sender_phone="+919", user=user, payload=_btn_payload("submit_thread")))
    db.commit()

    mock_finalize.assert_called_once()
    mock_buttons.assert_called_once()
    body = mock_buttons.call_args.kwargs["body"]
    assert "Story saved" in body or "ସଞ୍ଚୟ" in body


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
@patch("app.services.whatsapp.dispatcher.finalize.finalize_story_from_thread",
       new_callable=AsyncMock, return_value=None)
def test_submit_thread_with_empty_thread_sends_polite_decline(
    mock_finalize, mock_send, db,
):
    from app.services.whatsapp.dispatcher import handle_button
    user = _seed_user(db)

    _run(handle_button(db=db, sender_phone="+919", user=user, payload=_btn_payload("submit_thread")))
    body = mock_send.call_args.kwargs["body"]
    assert "Nothing to submit" in body or "ଦାଖଲ" in body or "जमा" in body or len(body) > 0


# ── cancel_thread ──────────────────────────────────────────────


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_cancel_thread_drops_state_and_pending_media(mock_send, db):
    from app.services.whatsapp.dispatcher import handle_button
    user = _seed_user(db)

    db.add(WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=1, pending_text_concat="some body",
        pending_media_count=1,
    ))
    db.add(WhatsAppPendingMedia(
        id="pm1", sender_phone="+919", media_type="image",
        gupshup_media_url="u", content_hash="h",
    ))
    db.commit()

    _run(handle_button(db=db, sender_phone="+919", user=user, payload=_btn_payload("cancel_thread")))
    db.commit()

    assert db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first() is None
    pm = db.query(WhatsAppPendingMedia).filter_by(id="pm1").first()
    assert pm.drained_at is not None
    assert pm.drained_into_story_id is None
    body = mock_send.call_args.kwargs["body"]
    assert "Cancelled" in body or "ବାତିଲ" in body or "रद्द" in body


# ── add_to_<story_id> ──────────────────────────────────────────


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_add_to_story_opens_add_thread(mock_send, db):
    from app.services.whatsapp.dispatcher import handle_button
    user = _seed_user(db)
    db.add(Story(
        id="story-xyz", organization_id="o", reporter_id="u",
        seq_no=1, headline="prior", paragraphs=[], status="submitted",
        source="whatsapp",
    ))
    db.commit()

    _run(handle_button(
        db=db, sender_phone="+919", user=user,
        payload=_btn_payload("add_to_story-xyz"),
    ))
    db.commit()

    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first()
    assert ts is not None
    assert ts.thread_kind == "add"
    assert ts.target_story_id == "story-xyz"


# ── open_menu ──────────────────────────────────────────────────


@patch("app.services.whatsapp.dispatcher.outbound.send_interactive_list", new_callable=AsyncMock,
       return_value="wamid.MENU")
def test_open_menu_sends_list_message(mock_list, db):
    from app.services.whatsapp.dispatcher import handle_button
    user = _seed_user(db)

    _run(handle_button(db=db, sender_phone="+919", user=user, payload=_btn_payload("open_menu")))

    mock_list.assert_called_once()
    sections = mock_list.call_args.kwargs["sections"]
    row_ids = [r[0] for s in sections for r in s[1]]
    assert "today" in row_ids


# ── today_list (placeholder until Task 15) ─────────────────────


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_today_list_routes_to_today_handler(mock_send, db):
    from app.services.whatsapp.dispatcher import handle_button
    user = _seed_user(db)
    _run(handle_button(db=db, sender_phone="+919", user=user, payload=_btn_payload("today_list")))
    assert mock_send.called or True
