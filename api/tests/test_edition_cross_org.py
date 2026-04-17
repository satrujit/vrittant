"""Security: edition story-assignment endpoints must not let org A reference org B's stories.

Vuln (pre-fix): assign_stories / add_story_to_page / remove_story_from_page only
verified that the *edition* belonged to the caller's org, not the *story_id*.
A reviewer could attach any story (by guessing UUIDs) to their own edition,
then read content, export-zip the IDML, etc.
"""

from datetime import date

from app.models.edition import Edition, EditionPage, EditionPageStory
from app.models.story import Story
from app.models.user import User


def _make_other_org_story(db) -> str:
    """Create a story owned by a different org and return its id."""
    rival_reporter = User(
        id="reporter-rival",
        name="Rival Reporter",
        phone="+910000000000",
        user_type="reporter",
        organization="Rival Org",
        organization_id="org-rival",
    )
    other = Story(
        id="story-other-org",
        reporter_id=rival_reporter.id,
        headline="Confidential rival headline",
        category="politics",
        paragraphs=[{"id": "p1", "text": "secret"}],
        status="approved",
        organization_id="org-rival",
    )
    db.add_all([rival_reporter, other])
    db.commit()
    return other.id


def _make_my_edition(db) -> tuple[str, str]:
    """Create an edition + page in the caller's org. Returns (edition_id, page_id)."""
    ed = Edition(
        id="ed-1",
        organization_id="org-test",
        publication_date=date(2026, 4, 17),
        title="Today",
    )
    page = EditionPage(id="page-1", edition_id="ed-1", page_number=1, page_name="Front", sort_order=0)
    db.add_all([ed, page])
    db.commit()
    return ed.id, page.id


# ── PUT /admin/editions/{eid}/pages/{pid}/stories ──

def test_assign_stories_rejects_cross_org_story(client, db, reviewer, auth_header):
    ed_id, page_id = _make_my_edition(db)
    foreign_story_id = _make_other_org_story(db)

    resp = client.put(
        f"/admin/editions/{ed_id}/pages/{page_id}/stories",
        json={"story_ids": [foreign_story_id]},
        headers=auth_header,
    )

    assert resp.status_code in (403, 404), (
        f"Expected 403/404, got {resp.status_code}: {resp.text}"
    )
    # Confirm no row was inserted
    rows = db.query(EditionPageStory).filter(EditionPageStory.edition_page_id == page_id).all()
    assert rows == [], f"Cross-org story was attached to page: {rows}"


# ── POST /admin/editions/{eid}/pages/{pid}/stories/{sid} ──

def test_add_story_to_page_rejects_cross_org_story(client, db, reviewer, auth_header):
    ed_id, page_id = _make_my_edition(db)
    foreign_story_id = _make_other_org_story(db)

    resp = client.post(
        f"/admin/editions/{ed_id}/pages/{page_id}/stories/{foreign_story_id}",
        headers=auth_header,
    )

    assert resp.status_code in (403, 404), (
        f"Expected 403/404, got {resp.status_code}: {resp.text}"
    )
    rows = db.query(EditionPageStory).filter(EditionPageStory.edition_page_id == page_id).all()
    assert rows == [], f"Cross-org story was attached: {rows}"


# ── Sanity: same-org story still works ──

def test_assign_stories_accepts_same_org_story(client, db, reviewer, sample_story, auth_header):
    ed_id, page_id = _make_my_edition(db)

    resp = client.put(
        f"/admin/editions/{ed_id}/pages/{page_id}/stories",
        json={"story_ids": [sample_story.id]},
        headers=auth_header,
    )

    assert resp.status_code == 200, resp.text
    rows = db.query(EditionPageStory).filter(EditionPageStory.edition_page_id == page_id).all()
    assert len(rows) == 1
    assert rows[0].story_id == sample_story.id
