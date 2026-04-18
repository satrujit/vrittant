"""Deactivating a reviewer (or changing their role away from reviewer) redistributes
their open assigned stories to other active reviewers.

Closed statuses (published, rejected) are NOT redistributed. If no replacement reviewer
is available, the story's `assigned_to` is nulled and no log row is written (because
`StoryAssignmentLog.to_user_id` is non-nullable).
"""
from app.models.story import Story
from app.models.story_assignment_log import StoryAssignmentLog
from app.models.user import User


def _make_user(db, *, uid, name, user_type="reviewer", is_active=True):
    u = User(
        id=uid, name=name, phone=name, user_type=user_type,
        organization="Test Org", organization_id="org-test",
        is_active=is_active,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_story(db, *, sid, reporter_id, assigned_to, status="submitted"):
    s = Story(
        id=sid, reporter_id=reporter_id, organization_id="org-test",
        headline=sid, paragraphs=[], status=status, assigned_to=assigned_to,
        assigned_match_reason="category",
    )
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_deactivate_reviewer_redistributes_open_stories(client, db, org_admin, org_admin_header):
    reporter = _make_user(db, uid="rep-r1", name="rep-r1", user_type="reporter")
    rev_a = _make_user(db, uid="rev-A", name="rev-A")
    rev_b = _make_user(db, uid="rev-B", name="rev-B")

    s1 = _make_story(db, sid="s-open-1", reporter_id=reporter.id, assigned_to=rev_a.id, status="submitted")
    s2 = _make_story(db, sid="s-open-2", reporter_id=reporter.id, assigned_to=rev_a.id, status="approved")

    resp = client.put(f"/admin/users/{rev_a.id}", json={"is_active": False}, headers=org_admin_header)
    assert resp.status_code == 200, resp.text

    db.expire_all()
    s1 = db.query(Story).filter(Story.id == s1.id).first()
    s2 = db.query(Story).filter(Story.id == s2.id).first()
    assert s1.assigned_to == rev_b.id
    assert s2.assigned_to == rev_b.id

    logs = db.query(StoryAssignmentLog).filter(
        StoryAssignmentLog.reason == "redistribute"
    ).all()
    assert len(logs) == 2
    for log in logs:
        assert log.from_user_id == rev_a.id
        assert log.to_user_id == rev_b.id
        assert log.assigned_by == org_admin.id


def test_deactivate_no_replacement_nulls_assigned_to(client, db, org_admin, org_admin_header):
    reporter = _make_user(db, uid="rep-r2", name="rep-r2", user_type="reporter")
    rev_a = _make_user(db, uid="rev-A2", name="rev-A2")

    s1 = _make_story(db, sid="s-open-3", reporter_id=reporter.id, assigned_to=rev_a.id, status="submitted")

    resp = client.put(f"/admin/users/{rev_a.id}", json={"is_active": False}, headers=org_admin_header)
    assert resp.status_code == 200, resp.text

    db.expire_all()
    s1 = db.query(Story).filter(Story.id == s1.id).first()
    assert s1.assigned_to is None
    assert s1.assigned_match_reason is None
    assert db.query(StoryAssignmentLog).filter(
        StoryAssignmentLog.story_id == s1.id, StoryAssignmentLog.reason == "redistribute"
    ).count() == 0


def test_deactivate_does_not_touch_closed_stories(client, db, org_admin, org_admin_header):
    reporter = _make_user(db, uid="rep-r3", name="rep-r3", user_type="reporter")
    rev_a = _make_user(db, uid="rev-A3", name="rev-A3")
    rev_b = _make_user(db, uid="rev-B3", name="rev-B3")

    pub = _make_story(db, sid="s-pub", reporter_id=reporter.id, assigned_to=rev_a.id, status="published")
    rej = _make_story(db, sid="s-rej", reporter_id=reporter.id, assigned_to=rev_a.id, status="rejected")

    resp = client.put(f"/admin/users/{rev_a.id}", json={"is_active": False}, headers=org_admin_header)
    assert resp.status_code == 200, resp.text

    db.expire_all()
    assert db.query(Story).filter(Story.id == pub.id).first().assigned_to == rev_a.id
    assert db.query(Story).filter(Story.id == rej.id).first().assigned_to == rev_a.id
    assert db.query(StoryAssignmentLog).filter(
        StoryAssignmentLog.reason == "redistribute"
    ).count() == 0


def test_role_change_reviewer_to_reporter_redistributes(client, db, org_admin, org_admin_header):
    reporter = _make_user(db, uid="rep-r4", name="rep-r4", user_type="reporter")
    rev_a = _make_user(db, uid="rev-A4", name="rev-A4")
    rev_b = _make_user(db, uid="rev-B4", name="rev-B4")

    s1 = _make_story(db, sid="s-open-4", reporter_id=reporter.id, assigned_to=rev_a.id, status="submitted")

    resp = client.put(f"/admin/users/{rev_a.id}/role", json={"user_type": "reporter"}, headers=org_admin_header)
    assert resp.status_code == 200, resp.text

    db.expire_all()
    s1 = db.query(Story).filter(Story.id == s1.id).first()
    assert s1.assigned_to == rev_b.id
    log = db.query(StoryAssignmentLog).filter(StoryAssignmentLog.story_id == s1.id).first()
    assert log is not None
    assert log.reason == "redistribute"
    assert log.from_user_id == rev_a.id
    assert log.to_user_id == rev_b.id
    assert log.assigned_by == org_admin.id


def test_role_change_reporter_to_reviewer_does_not_trigger(client, db, org_admin, org_admin_header):
    """Promoting a reporter to reviewer must NOT call redistribute (they had no assignments)."""
    rep = _make_user(db, uid="rep-promote", name="rep-promote", user_type="reporter")

    resp = client.put(f"/admin/users/{rep.id}/role", json={"user_type": "reviewer"}, headers=org_admin_header)
    assert resp.status_code == 200, resp.text

    assert db.query(StoryAssignmentLog).filter(
        StoryAssignmentLog.reason == "redistribute"
    ).count() == 0
