"""Content-level dedup for WhatsApp inbound payloads.

Catches the case where a reporter forwards the same image/text twice
in the same session (intentional or accidental WhatsApp re-send).
Distinct from `whatsapp_inbound_dedup` which keys on Gupshup's
message_id (only catches retries of the *same* webhook delivery, not
user-driven re-forwards).

For media, callers should hash the bytes (after downloading from
Gupshup). For text, callers should hash the post-strip body.
"""
from __future__ import annotations

import hashlib
import re

from sqlalchemy.orm import Session

from app.models.whatsapp_buffer import WhatsAppContentDedup


_WS_RE = re.compile(r"\s+")


def hash_text(text: str) -> str:
    """SHA256 of whitespace-normalised text. So 'a  b\\n' == 'a b'.

    Normalisation is intentionally aggressive: collapse all whitespace
    runs to a single space, trim. This means 'foo' and 'foo\\n\\n' are
    the same — accidental newlines (common in WhatsApp forwards) don't
    defeat dedup.
    """
    norm = _WS_RE.sub(" ", text).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def hash_bytes(data: bytes) -> str:
    """SHA256 of raw bytes. Caller responsible for downloading the
    media from Gupshup before hashing."""
    return hashlib.sha256(data).hexdigest()


def is_duplicate(db: Session, sender_phone: str, content_hash: str) -> bool:
    return db.query(WhatsAppContentDedup).filter_by(
        sender_phone=sender_phone, content_hash=content_hash,
    ).first() is not None


def mark_seen(db: Session, sender_phone: str, content_hash: str) -> None:
    """Idempotent. Postgres uses ON CONFLICT DO NOTHING; SQLite (test
    env) uses an existence-check before INSERT."""
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(WhatsAppContentDedup).values(
            sender_phone=sender_phone, content_hash=content_hash,
        ).on_conflict_do_nothing()
        db.execute(stmt)
        return
    # SQLite path (used in tests)
    if not is_duplicate(db, sender_phone, content_hash):
        db.add(WhatsAppContentDedup(
            sender_phone=sender_phone, content_hash=content_hash,
        ))
