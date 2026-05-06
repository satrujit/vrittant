"""Tests for handle_skip — polite decline for stickers/locations/contacts,
silent ignore for unknown types."""
import asyncio
from unittest.mock import AsyncMock, patch

from app.services.whatsapp.classifier import MessageKind


def _user_with_lang(db, lang):
    """Build a User with a populated org so resolve_lang returns `lang`."""
    from app.models.organization import Organization
    from app.models.user import User
    org = Organization(id="o-skip", name="X", slug="x-skip", default_language=lang)
    user = User(
        id="u-skip", phone="+91", name="N",
        organization="X", organization_id="o-skip", user_type="reporter",
        is_active=True,
    )
    db.add_all([org, user]); db.commit()
    db.refresh(user, ["org"])
    return user


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_skip_sticker_sends_decline_in_user_lang(mock_send, db):
    from app.services.whatsapp.dispatcher import handle_skip
    user = _user_with_lang(db, "or")

    asyncio.run(handle_skip(
        db=db, sender_phone="+91", user=user, kind=MessageKind.SKIP_STICKER,
    ))
    mock_send.assert_called_once()
    body = mock_send.call_args.kwargs["body"]
    # Odia version contains the unique Odia phrase
    assert "ଷ୍ଟିକର" in body or "ସ୍ଥାନ" in body


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_skip_location_sends_decline(mock_send, db):
    from app.services.whatsapp.dispatcher import handle_skip
    user = _user_with_lang(db, "en")

    asyncio.run(handle_skip(
        db=db, sender_phone="+91", user=user, kind=MessageKind.SKIP_LOCATION,
    ))
    body = mock_send.call_args.kwargs["body"]
    assert "Sticker/location" in body or "not saved" in body


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_skip_contact_sends_decline(mock_send, db):
    from app.services.whatsapp.dispatcher import handle_skip
    user = _user_with_lang(db, "en")

    asyncio.run(handle_skip(
        db=db, sender_phone="+91", user=user, kind=MessageKind.SKIP_CONTACT,
    ))
    mock_send.assert_called_once()


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_skip_other_does_not_reply(mock_send, db):
    """Unknown WhatsApp types like 'video_note' are silently ignored."""
    from app.services.whatsapp.dispatcher import handle_skip
    user = _user_with_lang(db, "en")

    asyncio.run(handle_skip(
        db=db, sender_phone="+91", user=user, kind=MessageKind.SKIP_OTHER,
    ))
    mock_send.assert_not_called()


@patch("app.services.whatsapp.dispatcher.outbound.send_text", new_callable=AsyncMock)
def test_skip_with_unknown_user_falls_back_to_or(mock_send, db):
    """If user is None (unregistered phone sent a sticker), fall back to
    the platform default 'or' rather than crashing."""
    from app.services.whatsapp.dispatcher import handle_skip

    asyncio.run(handle_skip(
        db=db, sender_phone="+91999", user=None, kind=MessageKind.SKIP_STICKER,
    ))
    # Should still reply (Odia default)
    mock_send.assert_called_once()
