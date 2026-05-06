"""Tests for the per-sender thread state service."""
from datetime import datetime, timedelta, timezone

from app.models.whatsapp_buffer import WhatsAppThreadState
from app.services.whatsapp.thread_state import (
    open_or_get, increment_text, increment_media, close, is_idle,
)


def test_open_or_get_creates_new_with_defaults(db):
    ts = open_or_get(db, "+91")
    db.commit()
    assert ts.thread_kind == "new"
    assert ts.target_story_id is None
    assert ts.pending_text_count == 0
    assert ts.pending_media_count == 0
    assert ts.pending_text_concat == ""
    assert ts.audio_warning_shown is False


def test_open_or_get_with_add_kind_and_target(db):
    ts = open_or_get(db, "+91", thread_kind="add", target_story_id="story-1")
    db.commit()
    assert ts.thread_kind == "add"
    assert ts.target_story_id == "story-1"


def test_open_or_get_reuses_existing_row(db):
    ts1 = open_or_get(db, "+91"); db.commit()
    started = ts1.thread_started_at
    ts2 = open_or_get(db, "+91"); db.commit()
    assert ts2.thread_started_at == started
    rows = db.query(WhatsAppThreadState).filter_by(sender_phone="+91").count()
    assert rows == 1


def test_increment_text_appends_concat(db):
    open_or_get(db, "+91")
    increment_text(db, "+91", "Hello world.")
    increment_text(db, "+91", "Second sentence.")
    db.commit()
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+91").first()
    assert ts.pending_text_count == 2
    assert "Hello world." in ts.pending_text_concat
    assert "Second sentence." in ts.pending_text_concat


def test_increment_media_bumps_count(db):
    open_or_get(db, "+91")
    increment_media(db, "+91")
    increment_media(db, "+91")
    db.commit()
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+91").first()
    assert ts.pending_media_count == 2


def test_increment_updates_last_message_at(db):
    open_or_get(db, "+91")
    db.commit()
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+91").first()
    # Backdate
    ts.last_message_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db.commit()
    increment_text(db, "+91", "x")
    db.commit()
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+91").first()
    # Should now be very recent
    delta = datetime.now(timezone.utc) - ts.last_message_at
    assert delta < timedelta(seconds=5)


def test_close_deletes_row(db):
    open_or_get(db, "+91"); db.commit()
    close(db, "+91"); db.commit()
    assert db.query(WhatsAppThreadState).filter_by(sender_phone="+91").first() is None


def test_close_when_no_state_is_noop(db):
    close(db, "+91"); db.commit()  # should not raise
    assert db.query(WhatsAppThreadState).count() == 0


def test_is_idle_returns_true_when_no_state(db):
    """No row means no active thread — definitely idle."""
    assert is_idle(db, "+91") is True


def test_is_idle_returns_true_for_old_thread(db):
    open_or_get(db, "+91")
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone="+91").first()
    ts.last_message_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db.commit()
    assert is_idle(db, "+91", idle_seconds=60) is True


def test_is_idle_returns_false_for_active_thread(db):
    open_or_get(db, "+91"); db.commit()
    assert is_idle(db, "+91", idle_seconds=60) is False
