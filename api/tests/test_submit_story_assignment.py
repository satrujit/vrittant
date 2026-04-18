"""Submitting a story auto-assigns it to a reviewer and writes an audit log row."""
from app.models.story import Story
from app.models.story_assignment_log import StoryAssignmentLog
from app.models.user import User


def _make_user(db, *, name, user_type="reviewer", area="", categories=None, regions=None):
    u = User(
        name=name, phone=name, user_type=user_type, area_name=area,
        organization_id="org1", organization="Org",
        categories=categories or [], regions=regions or [], is_active=True,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_draft(db, reporter, *, category=None):
    s = Story(reporter_id=reporter.id, organization_id="org1", category=category,
              paragraphs=[], status="draft")
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_submit_assigns_to_matching_reviewer(client, db, override_user):
    reporter = _make_user(db, name="rep", user_type="reporter")
    reviewer = _make_user(db, name="rev", categories=["sports"])
    draft = _make_draft(db, reporter, category="sports")
    override_user(reporter)

    resp = client.post(f"/stories/{draft.id}/submit")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["assigned_to"] == reviewer.id
    assert body["assigned_match_reason"] == "category"


def test_submit_writes_assignment_log(client, db, override_user):
    reporter = _make_user(db, name="rep2", user_type="reporter")
    reviewer = _make_user(db, name="rev2", categories=["sports"])
    draft = _make_draft(db, reporter, category="sports")
    override_user(reporter)

    client.post(f"/stories/{draft.id}/submit")
    log = db.query(StoryAssignmentLog).filter(StoryAssignmentLog.story_id == draft.id).first()
    assert log is not None
    assert log.from_user_id is None
    assert log.to_user_id == reviewer.id
    assert log.assigned_by is None
    assert log.reason == "auto"


def test_submit_no_reviewers_succeeds_with_null_assignee(client, db, override_user):
    reporter = _make_user(db, name="rep3", user_type="reporter")
    draft = _make_draft(db, reporter, category="sports")
    override_user(reporter)

    resp = client.post(f"/stories/{draft.id}/submit")
    assert resp.status_code == 200, resp.text
    s = db.query(Story).filter(Story.id == draft.id).first()
    assert s.status == "submitted"
    assert s.assigned_to is None
    assert (
        db.query(StoryAssignmentLog).filter(StoryAssignmentLog.story_id == draft.id).count() == 0
    )
