"""Tests for the get_owned_or_404 scope helper.

Centralized org-scoping helper introduced to prevent the IDOR class fixed in
commit 289820a — "fetch by id, filter by org, raise 404" was duplicated across
dozens of routers and one of them missed the org filter. These tests pin the
three required behaviors so future refactors can't regress the contract.
"""

import pytest
from fastapi import HTTPException

from app.models.organization import Organization
from app.models.story import Story
from app.models.user import User
from app.utils.scope import get_owned_or_404


def _make_story(db, story_id: str, org_id: str, reporter_id: str) -> Story:
    """Create a Story (and its required reporter) in the given org."""
    reporter = User(
        id=reporter_id,
        name=f"Reporter {reporter_id}",
        phone=f"+91{abs(hash(reporter_id)) % 10**10:010d}",
        user_type="reporter",
        organization=f"Org {org_id}",
        organization_id=org_id,
    )
    story = Story(
        id=story_id,
        reporter_id=reporter_id,
        headline="Test headline",
        category="politics",
        paragraphs=[{"id": "p1", "text": "Body."}],
        status="submitted",
        organization_id=org_id,
    )
    db.add_all([reporter, story])
    db.commit()
    return story


def test_returns_object_when_org_matches(db):
    _make_story(db, story_id="story-A", org_id="org-test", reporter_id="rep-A")

    result = get_owned_or_404(db, Story, "story-A", "org-test")

    assert result is not None
    assert result.id == "story-A"
    assert result.organization_id == "org-test"


def test_raises_404_when_id_missing(db):
    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Story, "story-does-not-exist", "org-test")

    assert exc_info.value.status_code == 404


def test_raises_404_when_org_mismatch(db):
    # Story exists, but in a different org than the caller's.
    # We deliberately return 404 (not 403) to avoid leaking existence —
    # a 403 would let a caller probe whether an id is real in another org.
    _make_story(db, story_id="story-rival", org_id="org-rival", reporter_id="rep-rival")

    with pytest.raises(HTTPException) as exc_info:
        get_owned_or_404(db, Story, "story-rival", "org-test")

    assert exc_info.value.status_code == 404


def test_raises_typeerror_for_non_org_scoped_model(db):
    # Organization itself has 'id' but NO 'organization_id' — it IS the org.
    # If a Phase 2 caller mistakenly passes such a model, we want a loud,
    # immediate TypeError instead of a confusing AttributeError surfacing
    # deep inside SQLAlchemy's filter expression.
    with pytest.raises(TypeError) as exc_info:
        get_owned_or_404(db, Organization, "org-test", "org-test")

    assert "Organization" in str(exc_info.value)
