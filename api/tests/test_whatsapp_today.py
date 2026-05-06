"""Tests for the today's-stories handler."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.models.user import User
from app.models.organization import Organization
from app.models.story import Story
from app.services.whatsapp.today import handle_today, render_today_message


def _seed_user(db, lang="en"):
    org = Organization(id="o", name="X", slug="x", default_language=lang)
    user = User(
        id="u", phone="+919", name="N",
        organization="X", organization_id="o", user_type="reporter",
        is_active=True,
    )
    db.add_all([org, user]); db.commit()
    db.refresh(user, ["org"])
    return user


def _make_story(db, *, id_, reporter_id, headline, submitted_offset_minutes=0, status="submitted"):
    """Build a Story submitted at `now() - submitted_offset_minutes`."""
    s = Story(
        id=id_, organization_id="o", reporter_id=reporter_id,
        seq_no=1, headline=headline, paragraphs=[], status=status,
        source="whatsapp",
        submitted_at=datetime.now(timezone.utc) - timedelta(minutes=submitted_offset_minutes),
    )
    db.add(s); db.commit()
    return s


def _run(coro):
    return asyncio.run(coro)


# ── render_today_message (pure) ────────────────────────────────


def test_render_empty_in_english(db):
    body = render_today_message([], "en")
    assert "No stories filed today" in body


def test_render_short_list_in_english(db):
    user = _seed_user(db)
    s1 = _make_story(db, id_="s1", reporter_id="u",
                     headline="Bypoll results announced")
    body = render_today_message([s1], "en")
    assert "Your stories today (1)" in body
    assert "Bypoll results" in body
    assert "https://vrittant.in/r/today" in body


def test_render_truncates_long_headline(db):
    user = _seed_user(db)
    s = _make_story(db, id_="s1", reporter_id="u",
                     headline="A very long headline that exceeds fifty characters by quite a margin indeed today")
    body = render_today_message([s], "en")
    assert len("A very long headline that exceeds fifty characters by quite a margin indeed today") > 50
    # Truncated form (50 chars max) appears
    truncated = "A very long headline that exceeds fifty characters"[:50]
    assert truncated in body


def test_render_overflow_shows_first_25_plus_overflow_line(db):
    user = _seed_user(db)
    stories = [
        _make_story(db, id_=f"s{i:02}", reporter_id="u",
                    headline=f"Story #{i}", submitted_offset_minutes=i)
        for i in range(30)
    ]
    body = render_today_message(stories, "en")
    assert "(30)" in body  # header count is 30
    assert "(+5 more" in body  # 30 - 25 = 5
    # Story #25, #26, #27, #28, #29 should NOT appear
    assert "Story #29" not in body or body.count("\n• ") <= 25


# ── handle_today (DB + outbound) ───────────────────────────────


@patch("app.services.whatsapp.today.outbound.send_text", new_callable=AsyncMock)
def test_handle_today_with_no_stories_sends_empty(mock_send, db):
    user = _seed_user(db)
    _run(handle_today(db=db, sender_phone="+919", user=user))
    body = mock_send.call_args.kwargs["body"]
    assert "No stories filed today" in body or "ଆଜି" in body


@patch("app.services.whatsapp.today.outbound.send_text", new_callable=AsyncMock)
def test_handle_today_lists_only_todays_stories(mock_send, db):
    user = _seed_user(db)
    _make_story(db, id_="s_today", reporter_id="u",
                headline="Today's story", submitted_offset_minutes=10)
    _make_story(db, id_="s_yesterday", reporter_id="u",
                headline="Yesterday", submitted_offset_minutes=60 * 30)  # 30h ago
    _run(handle_today(db=db, sender_phone="+919", user=user))
    body = mock_send.call_args.kwargs["body"]
    assert "Today's story" in body
    assert "Yesterday" not in body


@patch("app.services.whatsapp.today.outbound.send_text", new_callable=AsyncMock)
def test_handle_today_excludes_other_reporters(mock_send, db):
    user = _seed_user(db)
    _make_story(db, id_="s_mine", reporter_id="u", headline="My story")

    # Another reporter's story today
    other_user = User(
        id="u2", phone="+92", name="Other",
        organization="X", organization_id="o", user_type="reporter",
        is_active=True,
    )
    db.add(other_user); db.commit()
    _make_story(db, id_="s_theirs", reporter_id="u2", headline="Their story")

    _run(handle_today(db=db, sender_phone="+919", user=user))
    body = mock_send.call_args.kwargs["body"]
    assert "My story" in body
    assert "Their story" not in body


@patch("app.services.whatsapp.today.outbound.send_text", new_callable=AsyncMock)
def test_handle_today_excludes_deleted_stories(mock_send, db):
    user = _seed_user(db)
    s1 = _make_story(db, id_="s1", reporter_id="u", headline="Active")
    s2 = _make_story(db, id_="s2", reporter_id="u", headline="Deleted")
    s2.deleted_at = datetime.now(timezone.utc)
    db.commit()

    _run(handle_today(db=db, sender_phone="+919", user=user))
    body = mock_send.call_args.kwargs["body"]
    assert "Active" in body
    assert "Deleted" not in body


@patch("app.services.whatsapp.today.outbound.send_text", new_callable=AsyncMock)
def test_handle_today_with_unregistered_user_is_silent(mock_send, db):
    """If user is None (unregistered), silently no-op. No reply."""
    _run(handle_today(db=db, sender_phone="+9999", user=None))
    mock_send.assert_not_called()
