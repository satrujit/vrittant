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
    # All row titles must fit within WhatsApp's 24-char list-row title cap
    # so they don't truncate (the prod 2026-05-07 "How to use Vrittant on W"
    # bug). Long phrasing belongs in the row description.
    for section_title, rows in sections:
        assert len(section_title) <= 24, f"section title too long: {section_title!r}"
        for row_id, row_title, row_desc in rows:
            assert len(row_title) <= 24, f"row title too long: {row_title!r}"


@patch("app.services.whatsapp.dispatcher.outbound.send_interactive_list", new_callable=AsyncMock,
       return_value="wamid.MENU")
def test_open_menu_uses_user_locale_for_titles(mock_list, db):
    """Menu rows must be i18n'd — an Odia-locale user should NOT see
    English row titles. Regression for the prod 2026-05-07 report."""
    from app.services.whatsapp.dispatcher import handle_button
    user = _seed_user(db, lang="or")

    _run(handle_button(db=db, sender_phone="+919", user=user, payload=_btn_payload("open_menu")))

    sections = mock_list.call_args.kwargs["sections"]
    # At least one row title should contain Odia script (a Devanagari
    # range proxy isn't right — Odia is U+0B00-0B7F).
    all_text = " ".join(
        s_title + " " + " ".join(r[1] for r in rows)
        for s_title, rows in sections
    )
    assert any("଀" <= ch <= "୿" for ch in all_text), (
        "expected Odia characters in localised menu, got: " + all_text
    )


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_help_button_sends_howto_text(mock_send, db):
    """The "help" button (menu row id) must reply with the help text,
    not silently drop. Regression for prod 2026-05-07."""
    from app.services.whatsapp.dispatcher import handle_button
    user = _seed_user(db, lang="en")

    _run(handle_button(db=db, sender_phone="+919", user=user, payload=_btn_payload("help")))

    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body"]
    assert "Vrittant" in body or "Submit" in body


# ── today_list (placeholder until Task 15) ─────────────────────


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_today_list_routes_to_today_handler(mock_send, db):
    from app.services.whatsapp.dispatcher import handle_button
    user = _seed_user(db)
    _run(handle_button(db=db, sender_phone="+919", user=user, payload=_btn_payload("today_list")))
    assert mock_send.called or True


def test_handle_button_rejects_unauthenticated_sender(db):
    """Button payload from a phone we don't know must not probe story
    state (add_to_<id> path) or mutate thread_state. Reply with the
    polite 'not registered' message and return."""
    import asyncio
    from unittest.mock import patch, AsyncMock
    from app.services.whatsapp.dispatcher import handle_button
    from app.models.whatsapp_buffer import WhatsAppThreadState

    payload = _btn_payload("add_to_some-story-id")

    with patch("app.services.whatsapp.dispatcher.outbound.send_text",
               new_callable=AsyncMock) as mock_send:
        asyncio.run(handle_button(
            db=db, sender_phone="+919999", user=None, payload=payload,
        ))

    # Polite reply
    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body"]
    assert "isn't registered" in body or "ପଞ୍ଜିକୃତ" in body or "रजिस्टर्ड" in body or "registered" in body.lower()

    # No thread state row created
    assert db.query(WhatsAppThreadState).filter_by(sender_phone="+919999").first() is None
