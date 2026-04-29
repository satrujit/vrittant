"""Tests for the WordPress auto-publish pipeline.

We mock both the Anthropic translate call and the httpx WP REST calls
so the test runs with no network. The point is to exercise the
branching logic — create vs update vs skip-because-published vs
retract — and the sweep's retry/backoff bookkeeping.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.models.org_config import OrgConfig
from app.models.organization import Organization
from app.models.story import Story
from app.models.user import User
from app.services import wordpress_publisher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _seed_org_with_wp_config(db, org_id="org-test"):
    org = Organization(id=org_id, name=f"Test {org_id}", slug=org_id)
    db.add(org)
    db.add(OrgConfig(
        organization_id=org_id,
        categories=[],
        publication_types=[],
        page_suggestions=[],
        priority_levels=[],
        edition_schedule=[],
        edition_names=[],
        email_forwarders=[],
        whitelisted_contributors=[],
        wordpress_config={
            "base_url": "https://example.test",
            "username": "bot",
            "app_password_secret": "WP_TEST_APP_PASSWORD",
            "default_author_id": 7,
            "category_map": {"crime": 5},
        },
    ))
    db.commit()
    return org


def _seed_reporter(db, org_id="org-test"):
    user = User(
        id="user-test",
        name="Test Reporter",
        phone="+910000000001",
        user_type="reporter",
        area_name="Bhubaneswar",
        organization=org_id,
        organization_id=org_id,
    )
    db.add(user)
    db.commit()
    return user


def _seed_story(db, org_id="org-test", reporter_id="user-test", **overrides):
    defaults = dict(
        id="story-test",
        organization_id=org_id,
        reporter_id=reporter_id,
        headline="ଟେଷ୍ଟ ଖବର",
        category="crime",
        paragraphs=[{"id": "p1", "text": "ଭୁବନେଶ୍ଵର ସହରରେ ଆଜି ଏକ ଘଟଣା ଘଟିଲା।"}],
        status="approved",
        wp_push_status="pending",
        wp_push_attempts=0,
    )
    defaults.update(overrides)
    story = Story(**defaults)
    db.add(story)
    db.commit()
    return story


@pytest.fixture(autouse=True)
def _set_secret_env(monkeypatch):
    monkeypatch.setenv("WP_TEST_APP_PASSWORD", "test-app-password")


# Patch the chat function on the wordpress_publisher namespace so the
# translate helper resolves the mock during tests. The publisher imports
# anthropic_client as a module attribute.
@pytest.fixture
def mock_translate(monkeypatch):
    async def fake_chat(*args, **kwargs):
        return {
            "content": [{"type": "text", "text": json.dumps({
                "title": "Incident in Bhubaneswar",
                "body": "An incident took place in Bhubaneswar today.",
                "excerpt": "An incident took place in Bhubaneswar today.",
            })}],
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
    monkeypatch.setattr(wordpress_publisher.anthropic_client, "chat", fake_chat)


# ---------------------------------------------------------------------------
# push_or_update — create branch
# ---------------------------------------------------------------------------

def test_push_creates_new_post_when_no_wp_post_id(db, mock_translate):
    """Fresh approved story → POST /wp/v2/posts → wp_post_id stamped on story."""
    _seed_org_with_wp_config(db)
    _seed_reporter(db)
    story = _seed_story(db)

    fake_post_response = AsyncMock()
    fake_post_response.status_code = 201
    fake_post_response.json = lambda: {"id": 42, "link": "https://example.test/?p=42"}

    with patch("app.services.wordpress_publisher.httpx.AsyncClient") as MockClient:
        client = MockClient.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=fake_post_response)

        import asyncio
        result = asyncio.run(wordpress_publisher.push_or_update(db, story))

    assert result.status == "ok"
    assert result.wp_post_id == 42
    assert result.wp_url == "https://example.test/?p=42"


def test_push_skips_when_no_wp_config(db, mock_translate):
    """Org without wordpress_config → skipped_no_config, no HTTP calls."""
    org = Organization(id="org-noconfig", name="NC", slug="nc")
    db.add(org)
    db.add(OrgConfig(
        organization_id="org-noconfig",
        categories=[], publication_types=[], page_suggestions=[],
        priority_levels=[], edition_schedule=[], edition_names=[],
        email_forwarders=[], whitelisted_contributors=[],
    ))
    db.commit()
    _seed_reporter(db, org_id="org-noconfig")
    story = _seed_story(db, org_id="org-noconfig")

    import asyncio
    result = asyncio.run(wordpress_publisher.push_or_update(db, story))
    assert result.status == "skipped_no_config"


# ---------------------------------------------------------------------------
# push_or_update — update branch with WP-status guard
# ---------------------------------------------------------------------------

def test_update_skips_when_wp_already_published(db, mock_translate):
    """WP-side state=publish → don't clobber; story flagged skipped_wp_status_publish."""
    _seed_org_with_wp_config(db)
    _seed_reporter(db)
    story = _seed_story(db, wp_post_id=42)

    fake_get = AsyncMock()
    fake_get.status_code = 200
    fake_get.json = lambda: {"id": 42, "status": "publish"}
    fake_get.raise_for_status = lambda: None

    with patch("app.services.wordpress_publisher.httpx.AsyncClient") as MockClient:
        client = MockClient.return_value.__aenter__.return_value
        client.get = AsyncMock(return_value=fake_get)
        client.post = AsyncMock()  # should never be called

        import asyncio
        result = asyncio.run(wordpress_publisher.push_or_update(db, story))

    assert result.status == "skipped_wp_status_publish"
    client.post.assert_not_called()


def test_update_proceeds_when_wp_still_draft(db, mock_translate):
    """WP-side state=draft → POST update. Same endpoint, post_id in URL."""
    _seed_org_with_wp_config(db)
    _seed_reporter(db)
    story = _seed_story(db, wp_post_id=42, headline="Updated")

    fake_get = AsyncMock()
    fake_get.status_code = 200
    fake_get.json = lambda: {"id": 42, "status": "draft"}
    fake_get.raise_for_status = lambda: None
    fake_post = AsyncMock()
    fake_post.status_code = 200
    fake_post.json = lambda: {"id": 42, "link": "https://example.test/?p=42"}

    with patch("app.services.wordpress_publisher.httpx.AsyncClient") as MockClient:
        client = MockClient.return_value.__aenter__.return_value
        client.get = AsyncMock(return_value=fake_get)
        client.post = AsyncMock(return_value=fake_post)

        import asyncio
        result = asyncio.run(wordpress_publisher.push_or_update(db, story))

    assert result.status == "ok"
    # Update call hit the post-id-specific endpoint, not the collection.
    posted_url = client.post.call_args[0][0]
    assert posted_url.endswith("/wp/v2/posts/42")


# ---------------------------------------------------------------------------
# Sweep retry/backoff
# ---------------------------------------------------------------------------

def test_sweep_increments_attempts_and_marks_failed_after_max(db):
    """After MAX_ATTEMPTS failures, status flips to 'failed' and stays."""
    _seed_org_with_wp_config(db)
    _seed_reporter(db)
    # Exhaust attempts manually so the sweep's first run sees attempts=4
    # → increments to 5 → if it fails, stays failed (next sweep won't pick).
    story = _seed_story(db, wp_push_attempts=4)

    fail_mock = AsyncMock(return_value=wordpress_publisher.PushResult(status="failed", error="net down"))

    with patch("app.services.wordpress_publisher.push_or_update", fail_mock):
        import asyncio
        result = asyncio.run(wordpress_publisher.sweep_pending(db))
    db.commit()  # the real /internal/sweep-wp-push endpoint commits; mirror that here

    assert result["picked"] == 1
    assert fail_mock.call_count == 1
    db.refresh(story)
    assert story.wp_push_status == "failed"
    assert story.wp_push_attempts == 5

    # Subsequent sweep doesn't pick it up — attempts >= MAX_ATTEMPTS
    with patch("app.services.wordpress_publisher.push_or_update") as never:
        result2 = asyncio.run(wordpress_publisher.sweep_pending(db))
    assert result2["picked"] == 0
    never.assert_not_called()
