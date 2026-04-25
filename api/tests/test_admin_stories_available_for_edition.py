"""Regression: GET /admin/stories?available_for_edition=X must include stories
already placed on edition X, even when they are also placed on other editions.

Pre-fix the filter dropped any story present on *any other* edition. With
multi-edition placements (Pragativadi: a single story can live on Ed 1, 2, 6
the same day) that meant the bucket view for each edition silently lost the
shared stories.
"""
from datetime import date

from app.models.edition import Edition, EditionPage, EditionPageStory
from app.models.story import Story


def _seed(db, *, in_target: bool, in_other: bool) -> str:
    """Create a story plus two editions; place the story per the flags. Returns story_id."""
    target_ed = Edition(
        id="ed-target",
        organization_id="org-test",
        publication_date=date(2026, 4, 25),
        title="Target",
    )
    other_ed = Edition(
        id="ed-other",
        organization_id="org-test",
        publication_date=date(2026, 4, 25),
        title="Other",
    )
    target_page = EditionPage(
        id="pg-target", edition_id="ed-target", page_number=1, page_name="pg_1", sort_order=0
    )
    other_page = EditionPage(
        id="pg-other", edition_id="ed-other", page_number=1, page_name="pg_1", sort_order=0
    )
    story = Story(
        id="story-x",
        reporter_id="reporter-1",
        headline="Multi-edition story",
        category="politics",
        paragraphs=[{"id": "p1", "text": "hi"}],
        status="approved",
        organization_id="org-test",
    )
    db.add_all([target_ed, other_ed, target_page, other_page, story])
    db.commit()
    if in_target:
        db.add(EditionPageStory(edition_page_id="pg-target", story_id=story.id, sort_order=0))
    if in_other:
        db.add(EditionPageStory(edition_page_id="pg-other", story_id=story.id, sort_order=0))
    db.commit()
    return story.id


def _ids(resp):
    return {s["id"] for s in resp.json()["stories"]}


def test_includes_story_placed_on_both_target_and_other(
    client, db, reviewer, reporter, override_user, auth_header
):
    override_user(reviewer)
    sid = _seed(db, in_target=True, in_other=True)
    resp = client.get(
        "/admin/stories",
        params={"status": "approved", "available_for_edition": "ed-target"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert sid in _ids(resp), "story placed on target edition must appear even if also on other"


def test_excludes_story_placed_only_on_other_edition(
    client, db, reviewer, reporter, override_user, auth_header
):
    override_user(reviewer)
    sid = _seed(db, in_target=False, in_other=True)
    resp = client.get(
        "/admin/stories",
        params={"status": "approved", "available_for_edition": "ed-target"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert sid not in _ids(resp), "story exclusively on other edition must be excluded"


def test_includes_unplaced_story(
    client, db, reviewer, reporter, override_user, auth_header
):
    override_user(reviewer)
    sid = _seed(db, in_target=False, in_other=False)
    resp = client.get(
        "/admin/stories",
        params={"status": "approved", "available_for_edition": "ed-target"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert sid in _ids(resp)
