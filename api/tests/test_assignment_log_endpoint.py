"""GET /admin/stories/{story_id}/assignment-log endpoint."""
from app.models.story import Story
from app.models.user import User


def _mk_user(db, *, name, user_type="reviewer", org_id="org1", categories=None):
    u = User(name=name, phone=name, user_type=user_type, area_name="",
             organization_id=org_id, organization="Org",
             categories=categories or [], regions=[], is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _mk_draft(db, reporter, *, category=None, org_id="org1"):
    s = Story(reporter_id=reporter.id, organization_id=org_id, category=category,
              paragraphs=[], status="draft")
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_assignment_log_returns_entries_newest_first_with_names(client, db, override_user):
    reporter = _mk_user(db, name="rep", user_type="reporter")
    rev_a = _mk_user(db, name="rev_a", categories=["sports"])
    rev_b = _mk_user(db, name="rev_b")
    draft = _mk_draft(db, reporter, category="sports")

    # Auto-assign on submit (writes log row reason="auto", from_user_id=None, assigned_by=None, to=rev_a)
    override_user(reporter)
    resp = client.post(f"/stories/{draft.id}/submit")
    assert resp.status_code == 200, resp.text

    # Manual reassign: rev_a -> rev_b, performed by rev_a
    override_user(rev_a)
    resp = client.patch(f"/admin/stories/{draft.id}/assignee", json={"assignee_id": rev_b.id})
    assert resp.status_code == 200, resp.text

    # Now fetch log
    resp = client.get(f"/admin/stories/{draft.id}/assignment-log")
    assert resp.status_code == 200, resp.text
    entries = resp.json()
    assert isinstance(entries, list)
    assert len(entries) == 2

    # Newest first => manual entry comes before the auto one
    manual, auto = entries[0], entries[1]

    assert manual["reason"] == "manual"
    assert manual["from_user_id"] == rev_a.id
    assert manual["from_user_name"] == "rev_a"
    assert manual["to_user_id"] == rev_b.id
    assert manual["to_user_name"] == "rev_b"
    assert manual["assigned_by"] == rev_a.id
    assert manual["assigned_by_name"] == "rev_a"

    assert auto["reason"] == "auto"
    assert auto["from_user_id"] is None
    assert auto["from_user_name"] is None
    assert auto["to_user_id"] == rev_a.id
    assert auto["to_user_name"] == "rev_a"
    assert auto["assigned_by"] is None
    assert auto["assigned_by_name"] is None


def test_assignment_log_404_for_other_org_story(client, db, override_user):
    reporter = _mk_user(db, name="rep_o", user_type="reporter", org_id="org-other")
    other_story = _mk_draft(db, reporter, org_id="org-other")

    rev_a = _mk_user(db, name="rev_x", org_id="org1")
    override_user(rev_a)

    resp = client.get(f"/admin/stories/{other_story.id}/assignment-log")
    assert resp.status_code == 404
