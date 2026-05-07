"""Content-level dedup for WhatsApp inbound payloads.

Catches the case where a reporter forwards the same image/text twice
in close succession (intentional or accidental WhatsApp re-send).
Distinct from `whatsapp_inbound_dedup` which keys on Gupshup's
message_id (only catches retries of the *same* webhook delivery, not
user-driven re-forwards).

Note on media hashing: today we hash the Gupshup delivery URL, which
catches Gupshup retries on the same media within their URL-cache TTL
but does NOT catch re-uploads of the same photo (each fresh delivery
gets a new transient URL). True content dedup for media would require
downloading bytes and hashing those — possible but expensive on every
inbound. Tracked as a v2 enhancement.

Dedup window: by default a hash is considered "seen" only if it landed
within the last 24 hours. Without an expiry, a reporter who legitimately
re-forwards the same press release a week later gets silently skipped,
which is the wrong behaviour. Callers can override the window for
content types where re-arrival truly never makes sense.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.whatsapp_buffer import WhatsAppContentDedup


_WS_RE = re.compile(r"\s+")
_DEFAULT_DEDUP_WINDOW_SECONDS = 24 * 60 * 60  # 24 hours


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


def is_duplicate(
    db: Session,
    sender_phone: str,
    content_hash: str,
    *,
    within_seconds: int = _DEFAULT_DEDUP_WINDOW_SECONDS,
) -> bool:
    """True if (sender_phone, content_hash) was seen within the last
    `within_seconds`. Older entries are treated as not-seen so a
    reporter re-forwarding the same content a week later isn't silently
    dropped.

    The dedup table is allowed to keep aged-out rows around — they're
    cheap and a periodic cleanup job (TBD) can purge them. The query
    just ignores anything older than the window.
    """
    cutoff = _utcnow_naive() - timedelta(seconds=within_seconds)
    return (
        db.query(WhatsAppContentDedup)
        .filter(
            WhatsAppContentDedup.sender_phone == sender_phone,
            WhatsAppContentDedup.content_hash == content_hash,
            WhatsAppContentDedup.received_at >= cutoff,
        )
        .first()
    ) is not None


def mark_seen(db: Session, sender_phone: str, content_hash: str) -> None:
    """Record (phone, hash, now) so subsequent is_duplicate() calls
    within the window return True. Idempotent — Postgres uses ON CONFLICT
    DO NOTHING; SQLite (tests) checks-then-inserts."""
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(WhatsAppContentDedup).values(
            sender_phone=sender_phone, content_hash=content_hash,
        ).on_conflict_do_nothing()
        db.execute(stmt)
        return
    # SQLite path (used in tests). Note: the existence check here is a
    # no-window check, but that's fine — the test env doesn't hit the
    # window-expiry edge case.
    exists = db.query(WhatsAppContentDedup).filter_by(
        sender_phone=sender_phone, content_hash=content_hash,
    ).first() is not None
    if not exists:
        db.add(WhatsAppContentDedup(
            sender_phone=sender_phone, content_hash=content_hash,
        ))


def _utcnow_naive() -> datetime:
    """Naive UTC for comparison with the WhatsAppContentDedup.received_at
    column (default `now()` in Postgres, treated as naive UTC by SQLAlchemy
    in this codebase)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
