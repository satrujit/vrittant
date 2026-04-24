"""Tests for the bulk placement endpoint that the matrix UI uses.

PUT /admin/stories/{story_id}/placements — replace the full set of
(edition_id, page_id) placements for a story.
GET /admin/stories/{story_id}/placements — read current placements.
"""
from datetime import date

from app.models.edition import Edition, EditionPage, EditionPageStory
from app.models.story import Story
from app.models.user import User


def _make_edition(db, org_id, title, page_count=12):
    ed = Edition(
        organization_id=org_id,
        publication_date=date(2026, 4, 27),
        paper_type="daily",
        title=title,
        status="draft",
    )
    db.add(ed)
    db.flush()
    pages = []
    for i in range(1, page_count + 1):
        p = EditionPage(
            edition_id=ed.id,
            page_number=i,
            page_name=f"pg_{i}",
            sort_order=i,
        )
        db.add(p)
        pages.append(p)
    db.flush()
    return ed, pages


def _make_other_org_with_edition(db):
    """Create a rival org + reporter + edition, returns (org_id, edition, pages)."""
    rival_reporter = User(
        id="reporter-rival",
        name="Rival Reporter",
        phone="+910000000000",
        user_type="reporter",
        organization="Rival Org",
        organization_id="org-rival",
    )
    db.add(rival_reporter)
    db.flush()
    ed, pages = _make_edition(db, "org-rival", "Rival Ed")
    return "org-rival", ed, pages


def test_inserts_new_placements(client, db, reviewer, sample_story, auth_header):
    ed1, pages1 = _make_edition(db, "org-test", "Ed 1")
    ed2, pages2 = _make_edition(db, "org-test", "Ed 2", 16)
    db.commit()

    resp = client.put(
        f"/admin/stories/{sample_story.id}/placements",
        headers=auth_header,
        json={"placements": [
            {"edition_id": ed1.id, "page_id": pages1[2].id},
            {"edition_id": ed2.id, "page_id": pages2[2].id},
        ]},
    )
    assert resp.status_code == 200, resp.text
    rows = db.query(EditionPageStory).filter_by(story_id=sample_story.id).all()
    assert len(rows) == 2
    body = resp.json()
    assert len(body) == 2
    keys = {(p["edition_id"], p["page_id"]) for p in body}
    assert (ed1.id, pages1[2].id) in keys
    assert (ed2.id, pages2[2].id) in keys
    # Response carries titles/names
    for p in body:
        assert "edition_title" in p
        assert "page_name" in p


def test_diffs_correctly_removes_omitted(client, db, reviewer, sample_story, auth_header):
    ed1, pages1 = _make_edition(db, "org-test", "Ed 1")
    db.add(EditionPageStory(
        edition_page_id=pages1[2].id,
        story_id=sample_story.id,
        sort_order=0,
    ))
    db.commit()

    resp = client.put(
        f"/admin/stories/{sample_story.id}/placements",
        headers=auth_header,
        json={"placements": []},
    )
    assert resp.status_code == 200, resp.text
    assert db.query(EditionPageStory).filter_by(story_id=sample_story.id).count() == 0
    assert resp.json() == []


def test_idempotent_same_set(client, db, reviewer, sample_story, auth_header):
    ed1, pages1 = _make_edition(db, "org-test", "Ed 1")
    db.commit()

    payload = {"placements": [{"edition_id": ed1.id, "page_id": pages1[0].id}]}
    r1 = client.put(
        f"/admin/stories/{sample_story.id}/placements",
        headers=auth_header,
        json=payload,
    )
    assert r1.status_code == 200, r1.text
    r2 = client.put(
        f"/admin/stories/{sample_story.id}/placements",
        headers=auth_header,
        json=payload,
    )
    assert r2.status_code == 200, r2.text
    assert db.query(EditionPageStory).filter_by(story_id=sample_story.id).count() == 1


def test_rejects_cross_org_edition(client, db, reviewer, sample_story, auth_header):
    _, ed_other, pages_other = _make_other_org_with_edition(db)
    db.commit()

    resp = client.put(
        f"/admin/stories/{sample_story.id}/placements",
        headers=auth_header,
        json={"placements": [
            {"edition_id": ed_other.id, "page_id": pages_other[0].id},
        ]},
    )
    assert resp.status_code in (400, 403, 404), resp.text
    assert db.query(EditionPageStory).filter_by(story_id=sample_story.id).count() == 0


def test_rejects_cross_org_story(client, db, reviewer, auth_header):
    """A reviewer in org-test cannot manage placements for org-rival's stories."""
    rival_reporter = User(
        id="reporter-rival-2",
        name="Rival Reporter",
        phone="+910000099999",
        user_type="reporter",
        organization="Rival Org",
        organization_id="org-rival",
    )
    foreign = Story(
        id="story-foreign",
        reporter_id=rival_reporter.id,
        headline="Foreign",
        category="politics",
        paragraphs=[{"id": "p1", "text": "x"}],
        status="approved",
        organization_id="org-rival",
    )
    db.add_all([rival_reporter, foreign])
    db.commit()

    resp = client.put(
        f"/admin/stories/{foreign.id}/placements",
        headers=auth_header,
        json={"placements": []},
    )
    assert resp.status_code in (403, 404), resp.text


def test_get_returns_current_placements(client, db, reviewer, sample_story, auth_header):
    ed1, pages1 = _make_edition(db, "org-test", "Ed 1")
    db.add(EditionPageStory(
        edition_page_id=pages1[4].id,
        story_id=sample_story.id,
        sort_order=0,
    ))
    db.commit()

    resp = client.get(
        f"/admin/stories/{sample_story.id}/placements",
        headers=auth_header,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["edition_id"] == ed1.id
    assert body[0]["page_id"] == pages1[4].id
    assert body[0]["page_name"] == "pg_5"
    assert body[0]["edition_title"] == "Ed 1"


def test_get_empty_when_no_placements(client, db, reviewer, sample_story, auth_header):
    resp = client.get(
        f"/admin/stories/{sample_story.id}/placements",
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_rejects_cross_org_story(client, db, reviewer, auth_header):
    rival_reporter = User(
        id="reporter-rival-3",
        name="Rival Reporter",
        phone="+910000088888",
        user_type="reporter",
        organization="Rival Org",
        organization_id="org-rival",
    )
    foreign = Story(
        id="story-foreign-get",
        reporter_id=rival_reporter.id,
        headline="Foreign",
        category="politics",
        paragraphs=[{"id": "p1", "text": "x"}],
        status="approved",
        organization_id="org-rival",
    )
    db.add_all([rival_reporter, foreign])
    db.commit()

    resp = client.get(
        f"/admin/stories/{foreign.id}/placements",
        headers=auth_header,
    )
    assert resp.status_code in (403, 404)
