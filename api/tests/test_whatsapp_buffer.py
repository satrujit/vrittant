"""Tests for the pending-media buffer service."""
from datetime import datetime, timedelta, timezone

from app.models.whatsapp_buffer import WhatsAppPendingMedia
from app.services.whatsapp.buffer import (
    add_to_buffer, drain_for_sender, count_pending, expire_old,
)


def test_add_to_buffer_inserts_row(db):
    add_to_buffer(
        db, sender_phone="+91", media_type="image",
        gupshup_url="https://gupshup/abc", content_hash="h1",
    )
    db.commit()
    rows = db.query(WhatsAppPendingMedia).all()
    assert len(rows) == 1
    assert rows[0].media_type == "image"
    assert rows[0].drained_at is None


def test_add_to_buffer_records_caption_and_storage_url(db):
    add_to_buffer(
        db, sender_phone="+91", media_type="document",
        gupshup_url="https://gupshup/doc", content_hash="h2",
        caption="Press release",
        storage_url="gs://bucket/doc.pdf",
    )
    db.commit()
    row = db.query(WhatsAppPendingMedia).first()
    assert row.caption == "Press release"
    assert row.storage_url == "gs://bucket/doc.pdf"


def test_count_pending_excludes_drained(db):
    add_to_buffer(db, sender_phone="+91", media_type="image",
                  gupshup_url="u", content_hash="h")
    db.commit()
    assert count_pending(db, "+91") == 1

    drain_for_sender(db, "+91", story_id=None)
    db.commit()
    assert count_pending(db, "+91") == 0


def test_count_pending_scoped_to_sender(db):
    add_to_buffer(db, sender_phone="+91", media_type="image",
                  gupshup_url="u1", content_hash="h1")
    add_to_buffer(db, sender_phone="+92", media_type="image",
                  gupshup_url="u2", content_hash="h2")
    db.commit()
    assert count_pending(db, "+91") == 1
    assert count_pending(db, "+92") == 1


def test_drain_for_sender_marks_drained_and_returns_rows_in_order(db):
    add_to_buffer(db, sender_phone="+91", media_type="image",
                  gupshup_url="u1", content_hash="h1")
    db.commit()
    add_to_buffer(db, sender_phone="+91", media_type="document",
                  gupshup_url="u2", content_hash="h2")
    db.commit()
    add_to_buffer(db, sender_phone="+92", media_type="image",  # other sender
                  gupshup_url="u3", content_hash="h3")
    db.commit()

    drained = drain_for_sender(db, "+91", story_id=None)
    db.commit()

    assert len(drained) == 2
    assert all(r.drained_at is not None for r in drained)
    assert drained[0].gupshup_media_url == "u1"
    assert drained[1].gupshup_media_url == "u2"

    other = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+92").first()
    assert other.drained_at is None  # untouched


def test_drain_for_sender_links_story_id(db):
    add_to_buffer(db, sender_phone="+91", media_type="image",
                  gupshup_url="u", content_hash="h")
    db.commit()
    drain_for_sender(db, "+91", story_id="story-uuid-1")
    db.commit()
    row = db.query(WhatsAppPendingMedia).first()
    assert row.drained_into_story_id == "story-uuid-1"


def test_drain_for_sender_when_nothing_pending_returns_empty(db):
    drained = drain_for_sender(db, "+91", story_id=None)
    db.commit()
    assert drained == []


def test_expire_old_returns_rows_older_than_idle(db):
    """Media older than idle_seconds with no companion text is force-drained."""
    old = WhatsAppPendingMedia(
        sender_phone="+91", media_type="image",
        gupshup_media_url="u", content_hash="h",
        received_at=datetime.now(timezone.utc) - timedelta(seconds=120),
    )
    fresh = WhatsAppPendingMedia(
        sender_phone="+91", media_type="image",
        gupshup_media_url="u2", content_hash="h2",
        received_at=datetime.now(timezone.utc) - timedelta(seconds=5),
    )
    db.add_all([old, fresh])
    db.commit()

    expired = expire_old(db, idle_seconds=60)
    assert len(expired) == 1
    assert expired[0].sender_phone == "+91"
    assert expired[0].gupshup_media_url == "u"


def test_expire_old_excludes_already_drained(db):
    drained = WhatsAppPendingMedia(
        sender_phone="+91", media_type="image",
        gupshup_media_url="u", content_hash="h",
        received_at=datetime.now(timezone.utc) - timedelta(seconds=120),
        drained_at=datetime.now(timezone.utc),
    )
    db.add(drained)
    db.commit()

    assert expire_old(db, idle_seconds=60) == []
