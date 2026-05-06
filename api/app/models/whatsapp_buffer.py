"""SQLAlchemy models for the WhatsApp self-service tables landed by
migration 2026-05-06-whatsapp-self-service.sql.

ID columns are VARCHAR (not Postgres UUID type) — matches the convention
used elsewhere in this codebase (stories.id, users.id, etc.).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Boolean, Integer, Index,
)

from ..database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class WhatsAppPendingMedia(Base):
    """Buffers media (photo/PDF/audio/video) that arrives before its
    accompanying text in a WhatsApp forward thread. Drained on Submit;
    auto-finalized after a 60s idle window if text never arrives.
    """
    __tablename__ = "whatsapp_pending_media"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_phone = Column(String, nullable=False)
    media_type = Column(String, nullable=False)  # 'image' | 'document' | 'audio' | 'video'
    gupshup_media_url = Column(Text, nullable=False)
    storage_url = Column(Text)
    content_hash = Column(String)
    caption = Column(Text)
    received_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    drained_at = Column(DateTime(timezone=True))
    drained_into_story_id = Column(
        String, ForeignKey("stories.id", ondelete="SET NULL")
    )

    __table_args__ = (
        Index("ix_pending_media_sender_received", "sender_phone", "received_at"),
    )


class WhatsAppThreadState(Base):
    """Per-sender state for the active forward thread. One row per sender at
    any time. `interactive_msg_id` is the Gupshup message id of the
    [Submit][Cancel] interactive message, used to edit-in-place as more
    forwards arrive.
    """
    __tablename__ = "whatsapp_thread_state"

    sender_phone = Column(String, primary_key=True)
    thread_kind = Column(String, nullable=False, default="new")  # 'new' | 'add'
    target_story_id = Column(
        String, ForeignKey("stories.id", ondelete="SET NULL")
    )
    thread_started_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_message_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    pending_text_count = Column(Integer, nullable=False, default=0)
    pending_media_count = Column(Integer, nullable=False, default=0)
    pending_text_concat = Column(Text, nullable=False, default="")
    interactive_msg_id = Column(String)
    audio_warning_shown = Column(Boolean, nullable=False, default=False)


class WhatsAppContentDedup(Base):
    """Tracks the SHA256 of every inbound text/media payload per sender.
    Same hash seen twice within the dedup window is a duplicate forward —
    silently skipped. Distinct from `whatsapp_inbound_dedup` which keys on
    Gupshup's message_id (catches retries of the same delivery, not user-
    driven re-forwards).
    """
    __tablename__ = "whatsapp_content_dedup"

    sender_phone = Column(String, primary_key=True)
    content_hash = Column(String, primary_key=True)
    received_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
