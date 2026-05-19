"""Per-sender thread state service.

One row per sender at any time. The thread tracks pending text and media
counts so the [Submit][Cancel] interactive message can be edited in place
("Got 3 messages — 1 text + 2 photos"). Auto-close on 60s idle prevents
two unrelated forward groups from the same reporter falsely merging.

Caller is responsible for commits — these helpers only stage changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.whatsapp_buffer import WhatsAppThreadState


# SQLite (used in tests) drops timezone info on DateTime(timezone=True)
# columns. Re-attach UTC on load so callers can compare with aware
# datetimes (e.g. `datetime.now(timezone.utc) - ts.last_message_at`).
def _reattach_utc(target, *_args):
    for attr in ("thread_started_at", "last_message_at"):
        v = getattr(target, attr, None)
        if v is not None and v.tzinfo is None:
            setattr(target, attr, v.replace(tzinfo=timezone.utc))


event.listens_for(WhatsAppThreadState, "load")(_reattach_utc)
event.listens_for(WhatsAppThreadState, "refresh")(_reattach_utc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_aware(dt: datetime) -> datetime:
    """SQLite drops tz info; re-attach UTC if missing."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def open_or_get(
    db: Session,
    sender_phone: str,
    *,
    thread_kind: str = "new",
    target_story_id: Optional[str] = None,
) -> WhatsAppThreadState:
    """Return the existing thread row or create a fresh one.

    `thread_kind`/`target_story_id` are only honored when creating a new
    row. To switch an existing row to the 'add' kind, the caller should
    `close()` first then `open_or_get(..., thread_kind='add', ...)`.

    Uses a savepoint so a concurrent-INSERT race doesn't roll back the
    caller's outer transaction.
    """
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone=sender_phone).first()
    if ts is not None:
        return ts
    try:
        nested = db.begin_nested()          # SAVEPOINT
        ts = WhatsAppThreadState(
            sender_phone=sender_phone,
            thread_kind=thread_kind,
            target_story_id=target_story_id,
        )
        db.add(ts)
        db.flush()
        return ts
    except IntegrityError:
        nested.rollback()                   # only rolls back the savepoint
        ts = db.query(WhatsAppThreadState).filter_by(sender_phone=sender_phone).first()
        if ts is None:
            raise  # shouldn't happen — re-raise for visibility
        return ts


def increment_text(db: Session, sender_phone: str, text: str) -> None:
    """Append `text` to the thread's accumulated pending text and bump
    counters. Opens the thread if not already open."""
    ts = open_or_get(db, sender_phone)
    ts.pending_text_count = (ts.pending_text_count or 0) + 1
    if ts.pending_text_concat:
        ts.pending_text_concat = (ts.pending_text_concat + "\n\n" + text).strip()
    else:
        ts.pending_text_concat = text.strip()
    ts.last_message_at = _utcnow()


def increment_media(db: Session, sender_phone: str) -> None:
    """Bump the pending-media counter on the thread. The actual media
    rows live in whatsapp_pending_media; this only updates the counter
    that the [Submit][Cancel] message renders.
    """
    ts = open_or_get(db, sender_phone)
    ts.pending_media_count = (ts.pending_media_count or 0) + 1
    ts.last_message_at = _utcnow()


def close(db: Session, sender_phone: str) -> None:
    """Delete the thread state row. Idempotent."""
    db.query(WhatsAppThreadState).filter_by(sender_phone=sender_phone).delete()


def is_idle(db: Session, sender_phone: str, idle_seconds: int = 60) -> bool:
    """Return True if the thread has no activity newer than `idle_seconds`
    ago, OR no thread row exists at all (treated as idle).

    Used by the dispatcher: if a forward arrives and the prior thread is
    idle, close it before opening a fresh one. Prevents false-merge of
    two unrelated forward groups.
    """
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone=sender_phone).first()
    if ts is None:
        return True
    last = ts.last_message_at
    # SQLite returns naive datetimes; normalize to UTC-aware.
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    cutoff = _utcnow() - timedelta(seconds=idle_seconds)
    return last < cutoff
