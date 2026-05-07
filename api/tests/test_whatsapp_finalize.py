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


@patch("app.services.whatsapp.finalize._persist_media", new_callable=AsyncMock,
       return_value=("gs://bucket/img2", b"", "image/png", None))
def test_append_to_story_appends_text_paragraph(mock_media, db):
    from app.services.whatsapp.finalize import append_to_story
    user = _seed_user(db)

    # Seed an existing story with one text paragraph
    existing_para = {"id": "p1", "text": "Original body text here for the story."}
    s = Story(
        id="s_existing", organization_id="o", reporter_id="u",
        seq_no=1, headline="Existing", paragraphs=[existing_para],
        status="submitted", source="whatsapp",
    )
    db.add(s); db.commit()

    # Active add-mode thread targeting s_existing
    ts = WhatsAppThreadState(
        sender_phone="+919",
        thread_kind="add", target_story_id="s_existing",
        pending_text_count=1,
        pending_text_concat="Correction: BJP won 4 seats not 3.",
    )
    db.add(ts); db.commit()

    appended = _run(append_to_story(db=db, sender_phone="+919", user=user))
    db.commit()
    db.refresh(appended)

    assert appended is not None
    assert appended.id == "s_existing"
    # Original paragraph preserved + new one appended
    paragraph_texts = [p.get("text") for p in appended.paragraphs]
    assert "Original body text here for the story." in paragraph_texts
    assert "Correction: BJP won 4 seats not 3." in paragraph_texts
    # Thread state cleared
    assert db.query(WhatsAppThreadState).filter_by(sender_phone="+919").first() is None


@patch("app.services.whatsapp.finalize._persist_media", new_callable=AsyncMock,
       return_value=("gs://bucket/img2", b"", "image/png", None))
def test_append_to_story_appends_media_paragraph(mock_media, db):
    from app.services.whatsapp.finalize import append_to_story
    user = _seed_user(db)

    s = Story(
        id="s_existing", organization_id="o", reporter_id="u",
        seq_no=1, headline="Existing", paragraphs=[],
        status="submitted", source="whatsapp",
    )
    db.add(s); db.commit()

    ts = WhatsAppThreadState(
        sender_phone="+919",
        thread_kind="add", target_story_id="s_existing",
        pending_media_count=1,
    )
    pm = WhatsAppPendingMedia(
        id="pm1", sender_phone="+919", media_type="image",
        gupshup_media_url="https://gupshup/img2", content_hash="h",
    )
    db.add_all([ts, pm]); db.commit()

    appended = _run(append_to_story(db=db, sender_phone="+919", user=user))
    db.commit()
    db.refresh(appended)

    assert any(p.get("media_type") == "photo" for p in appended.paragraphs)
    pm_after = db.query(WhatsAppPendingMedia).filter_by(id="pm1").first()
    assert pm_after.drained_into_story_id == "s_existing"


def test_append_to_story_returns_none_when_no_thread(db):
    from app.services.whatsapp.finalize import append_to_story
    user = _seed_user(db)
    appended = _run(append_to_story(db=db, sender_phone="+919", user=user))
    assert appended is None


def test_append_to_story_returns_none_when_thread_kind_is_new(db):
    """If somehow the thread is in 'new' mode (not 'add'), don't try
    to append — caller should have routed to finalize_story_from_thread."""
    from app.services.whatsapp.finalize import append_to_story
    user = _seed_user(db)
    ts = WhatsAppThreadState(
        sender_phone="+919", thread_kind="new",
        pending_text_count=1, pending_text_concat="some text",
    )
    db.add(ts); db.commit()
    appended = _run(append_to_story(db=db, sender_phone="+919", user=user))
    assert appended is None


# ── pick_assignee integration ─────────────────────────────────


@patch("app.services.whatsapp.finalize._persist_media", new_callable=AsyncMock,
       return_value=("gs://bucket/x", b"", "image/png", None))
@patch("app.services.whatsapp.finalize.classify_category", new_callable=AsyncMock,
       return_value=None)
def test_finalize_auto_assigns_via_pick_assignee_for_reporter(mock_cat, mock_media, db):
    """Regression: dispatcher's finalize must call pick_assignee for
    reporter-submitted stories. Without this, every WA story landed
    UNASSIGNED and the editor had to manually pick a reviewer.
    """
    from app.services.whatsapp.finalize import finalize_story_from_thread

    org = Organization(id="o", name="X", slug="x", default_language="or")
    reporter = User(
        id="rep1", phone="+919", name="Reporter",
        area_name="Nayagarh",
        organization="X", organization_id="o", user_type="reporter",
        is_active=True,
    )
    # A reviewer in the same org whose `regions` contains "Nayagarh" —
    # the region-match step in pick_assignee should pick them.
    reviewer = User(
        id="rev1", phone="+918", name="ReviewerA",
        organization="X", organization_id="o", user_type="reviewer",
        is_active=True, regions=["Nayagarh"],
    )
    db.add_all([org, reporter, reviewer]); db.commit()
    db.refresh(reporter, ["org"])

    ts = WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=1,
        pending_text_concat="Some real news content from Nayagarh district today happening now.",
        pending_media_count=0,
    )
    db.add(ts); db.commit()

    story = _run(finalize_story_from_thread(db=db, sender_phone="+919", user=reporter))
    db.commit()
    db.refresh(story)

    assert story.assigned_to == "rev1"
    assert story.assigned_match_reason == "region"


@patch("app.services.whatsapp.finalize._persist_media", new_callable=AsyncMock,
       return_value=("gs://bucket/x", b"", "image/png", None))
@patch("app.services.whatsapp.finalize.classify_category", new_callable=AsyncMock,
       return_value=None)
def test_finalize_leaves_unassigned_when_no_reviewers(mock_cat, mock_media, db):
    """If the org has zero active reviewers, story still gets created
    but assigned_to stays None — surfaces in the unassigned queue
    rather than 5xx-ing the webhook."""
    from app.services.whatsapp.finalize import finalize_story_from_thread

    org = Organization(id="o", name="X", slug="x", default_language="or")
    reporter = User(
        id="rep1", phone="+919", name="Reporter",
        organization="X", organization_id="o", user_type="reporter",
        is_active=True,
    )
    db.add_all([org, reporter]); db.commit()
    db.refresh(reporter, ["org"])

    ts = WhatsAppThreadState(
        sender_phone="+919",
        pending_text_count=1,
        pending_text_concat="Some real news content from this reporter today happening now here.",
    )
    db.add(ts); db.commit()

    story = _run(finalize_story_from_thread(db=db, sender_phone="+919", user=reporter))
    db.commit()
    db.refresh(story)

    assert story is not None  # story still created
    assert story.assigned_to is None
    assert story.assigned_match_reason is None
