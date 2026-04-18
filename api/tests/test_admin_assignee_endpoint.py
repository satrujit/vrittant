"""PATCH /admin/stories/{id}/assignee and audit log behavior."""
from app.models.story import Story
from app.models.story_assignment_log import StoryAssignmentLog
from app.models.user import User


def _mk_user(db, *, name, user_type="reviewer"):
    u = User(name=name, phone=name, user_type=user_type, area_name="",
             organization_id="org1", organization="Org",
             categories=[], regions=[], is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _mk_story_assigned(db, reporter_id, assignee_id):
    s = Story(reporter_id=reporter_id, organization_id="org1",
              status="submitted", paragraphs=[], assigned_to=assignee_id,
              assigned_match_reason="category")
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_reassign_updates_story(client, db, override_user):
    reporter = _mk_user(db, name="rep", user_type="reporter")
    rev_a = _mk_user(db, name="a")
    rev_b = _mk_user(db, name="b")
    story = _mk_story_assigned(db, reporter.id, rev_a.id)
    override_user(rev_a)

    resp = client.patch(f"/admin/stories/{story.id}/assignee",
                        json={"assignee_id": rev_b.id})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["assigned_to"] == rev_b.id
    assert body["assigned_match_reason"] == "manual"


def test_reassign_writes_log(client, db, override_user):
    reporter = _mk_user(db, name="rep2", user_type="reporter")
    rev_a = _mk_user(db, name="a2")
    rev_b = _mk_user(db, name="b2")
    story = _mk_story_assigned(db, reporter.id, rev_a.id)
    override_user(rev_a)

    client.patch(f"/admin/stories/{story.id}/assignee", json={"assignee_id": rev_b.id})
    log = (db.query(StoryAssignmentLog)
           .filter(StoryAssignmentLog.story_id == story.id, StoryAssignmentLog.reason == "manual")
           .first())
    assert log is not None
    assert log.from_user_id == rev_a.id
    assert log.to_user_id == rev_b.id
    assert log.assigned_by == rev_a.id


def test_reassign_rejects_non_reviewer_assignee(client, db, override_user):
    reporter = _mk_user(db, name="rep3", user_type="reporter")
    rev_a = _mk_user(db, name="a3")
    story = _mk_story_assigned(db, reporter.id, rev_a.id)
    override_user(rev_a)

    resp = client.patch(f"/admin/stories/{story.id}/assignee",
                        json={"assignee_id": reporter.id})
    assert resp.status_code == 400


def test_reassign_404_for_missing_story(client, db, override_user):
    rev_a = _mk_user(db, name="a4")
    rev_b = _mk_user(db, name="b4")
    override_user(rev_a)

    resp = client.patch("/admin/stories/nonexistent/assignee",
                        json={"assignee_id": rev_b.id})
    assert resp.status_code == 404
