"""Lock in the new layout-completion step.

Workflow rule: ``layout_completed`` only follows ``approved``. Anything
else (Reported, Rejected, Flagged, Published) cannot jump straight into
the layout state — that would defeat the whole point of the gate.

Also verify ``in_progress`` is no longer a writable status, since it was
collapsed into ``submitted`` in the 2026-04-23 backfill.
"""
from app.models.story import Story


def _story(reporter_id: str, status: str, sid: str = "story-lc-1") -> Story:
    return Story(
        id=sid,
        reporter_id=reporter_id,
        organization_id="org-test",
        headline="LC story",
        paragraphs=[{"id": "p1", "text": "body"}],
        status=status,
    )


def test_approved_can_move_to_layout_completed(client, db, reviewer, reporter, auth_header):
    story = _story(reporter.id, status="approved", sid="story-lc-ok")
    db.add(story)
    db.commit()

    resp = client.put(
        f"/admin/stories/{story.id}/status",
        json={"status": "layout_completed"},
        headers=auth_header,
    )
    assert resp.status_code == 200, resp.text

    db.refresh(story)
    assert story.status == "layout_completed"
    # layout_completed is a terminal-style status — attribution stays.
    assert story.reviewed_by == reviewer.id
    assert story.reviewed_at is not None


def test_submitted_cannot_skip_to_layout_completed(client, db, reviewer, reporter, auth_header):
    story = _story(reporter.id, status="submitted", sid="story-lc-skip")
    db.add(story)
    db.commit()

    resp = client.put(
        f"/admin/stories/{story.id}/status",
        json={"status": "layout_completed"},
        headers=auth_header,
    )
    assert resp.status_code == 400, resp.text
    assert "approved" in resp.json()["detail"].lower()

    db.refresh(story)
    assert story.status == "submitted"


def test_rejected_cannot_jump_to_layout_completed(client, db, reviewer, reporter, auth_header):
    story = _story(reporter.id, status="rejected", sid="story-lc-rej")
    db.add(story)
    db.commit()

    resp = client.put(
        f"/admin/stories/{story.id}/status",
        json={"status": "layout_completed"},
        headers=auth_header,
    )
    assert resp.status_code == 400, resp.text


def test_layout_completed_can_move_to_published(client, db, reviewer, reporter, auth_header):
    """Published is unrestricted — any allowed status can promote into it."""
    story = _story(reporter.id, status="layout_completed", sid="story-lc-pub")
    db.add(story)
    db.commit()

    resp = client.put(
        f"/admin/stories/{story.id}/status",
        json={"status": "published"},
        headers=auth_header,
    )
    assert resp.status_code == 200, resp.text

    db.refresh(story)
    assert story.status == "published"


def test_in_progress_no_longer_a_writable_status(client, db, reviewer, reporter, auth_header):
    """`in_progress` was collapsed into `submitted` — the API must now
    refuse it to keep the workflow surface small."""
    story = _story(reporter.id, status="approved", sid="story-lc-inp")
    db.add(story)
    db.commit()

    resp = client.put(
        f"/admin/stories/{story.id}/status",
        json={"status": "in_progress"},
        headers=auth_header,
    )
    assert resp.status_code == 400, resp.text


def test_flagged_is_writable(client, db, reviewer, reporter, auth_header):
    """Flagged is a real reviewer outcome alongside approved/rejected."""
    story = _story(reporter.id, status="submitted", sid="story-lc-flag")
    db.add(story)
    db.commit()

    resp = client.put(
        f"/admin/stories/{story.id}/status",
        json={"status": "flagged"},
        headers=auth_header,
    )
    assert resp.status_code == 200, resp.text

    db.refresh(story)
    assert story.status == "flagged"
    assert story.reviewed_by == reviewer.id


def test_create_blank_now_starts_as_submitted(client, db, auth_header):
    """Editor-created stories no longer enter `in_progress` limbo —
    they go straight onto the Reported queue."""
    resp = client.post("/admin/stories/create-blank", headers=auth_header)
    assert resp.status_code == 200, resp.text
    story_id = resp.json()["story_id"]

    story = db.query(Story).filter(Story.id == story_id).one()
    assert story.status == "submitted"
    assert story.submitted_at is not None
