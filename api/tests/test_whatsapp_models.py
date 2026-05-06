import pytest
from sqlalchemy.exc import IntegrityError
from app.models.whatsapp_buffer import (
    WhatsAppPendingMedia, WhatsAppThreadState, WhatsAppContentDedup,
)


def test_pending_media_can_be_inserted_and_queried(db):
    pm = WhatsAppPendingMedia(
        sender_phone="+919437115223",
        media_type="image",
        gupshup_media_url="https://media.gupshup.io/abc",
        content_hash="sha256-deadbeef",
    )
    db.add(pm); db.commit()
    found = db.query(WhatsAppPendingMedia).filter_by(sender_phone="+919437115223").first()
    assert found is not None
    assert found.media_type == "image"
    assert found.drained_at is None
    # id should be auto-populated as a UUID-as-string
    assert isinstance(found.id, str)
    assert len(found.id) == 36  # UUID-string length


def test_thread_state_defaults(db):
    ts = WhatsAppThreadState(sender_phone="+919437115223")
    db.add(ts); db.commit()
    found = db.query(WhatsAppThreadState).filter_by(sender_phone="+919437115223").first()
    assert found.thread_kind == "new"
    assert found.pending_text_count == 0
    assert found.pending_media_count == 0
    assert found.pending_text_concat == ""
    assert found.audio_warning_shown is False


def test_content_dedup_primary_key_prevents_duplicates(db):
    db.add(WhatsAppContentDedup(sender_phone="+91", content_hash="x"))
    db.commit()
    db.add(WhatsAppContentDedup(sender_phone="+91", content_hash="x"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_organization_has_default_language(db):
    from app.models.organization import Organization
    org = Organization(id="o1", name="X", slug="x")
    db.add(org); db.commit()
    found = db.query(Organization).filter_by(id="o1").first()
    assert found.default_language == "or"


def test_organization_default_language_can_be_set(db):
    from app.models.organization import Organization
    org = Organization(id="o2", name="Y", slug="y", default_language="hi")
    db.add(org); db.commit()
    found = db.query(Organization).filter_by(id="o2").first()
    assert found.default_language == "hi"


def test_story_has_whatsapp_confirm_message_id(db):
    """The whatsapp_confirm_message_id column is nullable and addressable."""
    from app.models.story import Story
    # Story has many required fields; just exercise the column on a SELECT
    # of a synthetic row inserted via Core to skip the validator chain.
    from sqlalchemy import insert
    db.execute(insert(Story.__table__).values(
        id="story-test-1",
        reporter_id="u1",
        organization_id="o1",
        headline="x",
        paragraphs=[],
        status="submitted",
        whatsapp_confirm_message_id="wamid.HBgM...",
    ))
    db.commit()
    found = db.query(Story).filter_by(id="story-test-1").first()
    assert found is not None
    assert found.whatsapp_confirm_message_id == "wamid.HBgM..."
