"""Tests for finalize_story_from_thread."""
import asyncio
from unittest.mock import AsyncMock, patch

from app.models.user import User
from app.models.organization import Organization
from app.models.story import Story
from app.models.whatsapp_buffer import WhatsAppPendingMedia, WhatsAppThreadState


def _seed_user(db):
    org = Organization(id="o", name="X", slug="x", default_language="or")
    user = User(
        id="u", phone="+919", name="N",
        organization="X", organization_id="o", user_type="reporter",
        is_active=True,
    )
    db.add_all([org, user]); db.commit()
    db.refresh(user, ["org"])
    return user


def _run(coro):
    return asyncio.run(coro)


@patch("app.services.whatsapp.finalize._persist_media", new_callable=AsyncMock,
       return_value=("gs://bucket/copy", b"", "image/png", None))
@patch("app.services.whatsapp.finalize.classify_category", new_callable=AsyncMock,
       return_value="general")
def test_finalize_creates_story_with_text_paragraph(mock_cat, mock_media, db):
    from app.services.whatsapp.finalize import finalize_story_from_thread
    user = _seed_user(db)

    ts = WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=1,
        pending_text_concat="Bypoll results announced today across the state with BJP winning three.",
        pending_media_count=0,
    )
    db.add(ts); db.commit()

    story = _run(finalize_story_from_thread(db=db, sender_phone="+919", user=user))
    db.commit()
    db.refresh(story)

    assert story is not None
    assert story.reporter_id == "u"
    assert story.organization_id == "o"
    assert story.status == "submitted"
    assert story.source == "whatsapp"
    assert "Bypoll results" in (story.headline or "")
    assert len(story.paragraphs) == 1
    assert "Bypoll results" in story.paragraphs[0]["text"]
    assert db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first() is None


@patch("app.services.whatsapp.finalize._persist_media", new_callable=AsyncMock,
       return_value=("gs://bucket/img1", b"", "image/png", None))
@patch("app.services.whatsapp.finalize.classify_category", new_callable=AsyncMock,
       return_value="general")
def test_finalize_drains_buffered_media(mock_cat, mock_media, db):
    from app.services.whatsapp.finalize import finalize_story_from_thread
    user = _seed_user(db)

    ts = WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=1,
        pending_text_concat="A long enough body for a story headline match here today.",
        pending_media_count=1,
    )
    pm = WhatsAppPendingMedia(
        id="pm1",
        sender_phone="+919",
        media_type="image",
        gupshup_media_url="https://gupshup/img1",
        content_hash="h1",
    )
    db.add_all([ts, pm]); db.commit()

    story = _run(finalize_story_from_thread(db=db, sender_phone="+919", user=user))
    db.commit()
    db.refresh(story)

    paragraph_types = [p.get("media_type") for p in story.paragraphs]
    assert "photo" in paragraph_types
    pm_after = db.query(WhatsAppPendingMedia).filter_by(id="pm1").first()
    assert pm_after.drained_at is not None
    assert pm_after.drained_into_story_id == story.id


@patch("app.services.whatsapp.finalize._persist_media", new_callable=AsyncMock,
       return_value=("gs://bucket/x", b"", "image/png", None))
@patch("app.services.whatsapp.finalize.classify_category", new_callable=AsyncMock,
       return_value=None)
def test_finalize_returns_none_when_thread_empty(mock_cat, mock_media, db):
    from app.services.whatsapp.finalize import finalize_story_from_thread
    user = _seed_user(db)

    ts = WhatsAppThreadState(sender_phone="+919")
    db.add(ts); db.commit()

    story = _run(finalize_story_from_thread(db=db, sender_phone="+919", user=user))
    assert story is None
