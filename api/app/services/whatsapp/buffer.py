"""Universal media buffer.

Media (photo/PDF/audio/video) that arrives before its text companion is
stashed here so a multi-message forward thread doesn't split into N
separate stories. Drained on Submit, or auto-finalized after a 60s
idle window if no text ever arrives (via expire_old).

Caller is responsible for:
- computing content_hash before insert (use services.whatsapp.dedup)
- copying the media to GCS and setting storage_url after download
- committing the session after add/drain (these helpers don't commit)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.whatsapp_buffer import WhatsAppPendingMedia


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_to_buffer(
    db: Session,
    *,
    sender_phone: str,
    media_type: str,
    gupshup_url: str,
    content_hash: Optional[str] = None,
    caption: Optional[str] = None,
    storage_url: Optional[str] = None,
) -> WhatsAppPendingMedia:
    """Insert a row. Caller commits."""
    row = WhatsAppPendingMedia(
        sender_phone=sender_phone,
        media_type=media_type,
        gupshup_media_url=gupshup_url,
        storage_url=storage_url,
        content_hash=content_hash,
        caption=caption,
    )
    db.add(row)
    return row


def count_pending(db: Session, sender_phone: str) -> int:
    """Count rows for `sender_phone` that haven't been drained."""
    return db.query(WhatsAppPendingMedia).filter(
        WhatsAppPendingMedia.sender_phone == sender_phone,
        WhatsAppPendingMedia.drained_at.is_(None),
    ).count()


def drain_for_sender(
    db: Session,
    sender_phone: str,
    *,
    story_id: Optional[str],
) -> List[WhatsAppPendingMedia]:
    """Mark all pending media for `sender_phone` as drained into
    `story_id`. Pass `story_id=None` to discard (Cancel path). Returns
    the rows in receipt order.

    Caller commits.
    """
    rows = db.query(WhatsAppPendingMedia).filter(
        WhatsAppPendingMedia.sender_phone == sender_phone,
        WhatsAppPendingMedia.drained_at.is_(None),
    ).order_by(WhatsAppPendingMedia.received_at).all()
    now = _utcnow()
    for r in rows:
        r.drained_at = now
        r.drained_into_story_id = story_id
    return rows


def expire_old(
    db: Session,
    idle_seconds: int = 60,
) -> List[WhatsAppPendingMedia]:
    """Find pending media older than `idle_seconds`. Caller is responsible
    for finalizing each as a media-only story.

    A nightly cron or on-arrival sweep can call this. Returns rows; does
    not mutate them — caller decides whether to drain or just observe.
    """
    cutoff = _utcnow() - timedelta(seconds=idle_seconds)
    return db.query(WhatsAppPendingMedia).filter(
        WhatsAppPendingMedia.drained_at.is_(None),
        WhatsAppPendingMedia.received_at < cutoff,
    ).all()
