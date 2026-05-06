"""Tests for the content-level dedup helpers."""
from app.services.whatsapp.dedup import (
    hash_text, hash_bytes, is_duplicate, mark_seen,
)


# ── hashing ────────────────────────────────────────────────────


def test_hash_text_is_deterministic():
    assert hash_text("hello world") == hash_text("hello world")


def test_hash_text_returns_64_char_hex():
    h = hash_text("anything")
    assert len(h) == 64
    int(h, 16)  # raises if not hex


def test_hash_text_normalises_whitespace():
    """'a  b\\n' should hash equal to 'a b' so trivial whitespace
    differences (WhatsApp trailing newlines, double-space typos) don't
    defeat dedup."""
    assert hash_text("hello  world\n") == hash_text("hello world")


def test_hash_text_normalises_leading_trailing():
    assert hash_text("  hello  ") == hash_text("hello")


def test_hash_text_distinct_messages_distinct_hashes():
    assert hash_text("foo") != hash_text("bar")


def test_hash_bytes_is_deterministic():
    assert hash_bytes(b"abc") == hash_bytes(b"abc")


def test_hash_bytes_distinct_inputs_distinct_hashes():
    assert hash_bytes(b"abc") != hash_bytes(b"abd")


# ── DB-level dedup ─────────────────────────────────────────────


def test_is_duplicate_returns_false_when_unseen(db):
    assert is_duplicate(db, "+91", "deadbeef") is False


def test_is_duplicate_returns_true_after_mark_seen(db):
    mark_seen(db, "+91", "deadbeef"); db.commit()
    assert is_duplicate(db, "+91", "deadbeef") is True


def test_mark_seen_idempotent(db):
    """Calling mark_seen twice with the same args should not raise."""
    mark_seen(db, "+91", "x"); db.commit()
    mark_seen(db, "+91", "x"); db.commit()
    # one row only
    from app.models.whatsapp_buffer import WhatsAppContentDedup
    assert db.query(WhatsAppContentDedup).count() == 1


def test_mark_seen_different_phones_not_collision(db):
    mark_seen(db, "+91", "h"); mark_seen(db, "+92", "h"); db.commit()
    assert is_duplicate(db, "+91", "h") is True
    assert is_duplicate(db, "+92", "h") is True
