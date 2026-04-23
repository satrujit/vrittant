"""Capture WHO and WHEN reviewed a story when status moves to a terminal state.

Reverting a story back to ``submitted`` (the only non-terminal status a
reviewer can target) clears the attribution so it is unambiguous who
currently owns the decision.
"""
from app.models.story import Story


def test_status_change_to_approved_records_reviewer(client, db, reviewer, reporter, auth_header):
    story = Story(
        id="story-attr-1",
        reporter_id=reporter.id,
        organization_id="org-test",
        headline="Pending Story",
        paragraphs=[{"id": "p1", "text": "body"}],
        status="submitted",
    )
    db.add(story)
    db.commit()

    resp = client.put(
        f"/admin/stories/{story.id}/status",
        json={"status": "approved"},
        headers=auth_header,
    )
    assert resp.status_code == 200, resp.text

    db.refresh(story)
    assert story.reviewed_by == reviewer.id
    assert story.reviewed_at is not None


def test_status_revert_to_submitted_clears_reviewer(client, db, reviewer, reporter, auth_header):
    story = Story(
        id="story-attr-2",
        reporter_id=reporter.id,
        organization_id="org-test",
        headline="Approved Story",
        paragraphs=[{"id": "p1", "text": "body"}],
        status="approved",
        reviewed_by=reviewer.id,
    )
    db.add(story)
    db.commit()

    resp = client.put(
        f"/admin/stories/{story.id}/status",
        json={"status": "submitted"},
        headers=auth_header,
    )
    assert resp.status_code == 200, resp.text

    db.refresh(story)
    assert story.reviewed_by is None
    assert story.reviewed_at is None
