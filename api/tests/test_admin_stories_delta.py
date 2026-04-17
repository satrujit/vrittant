"""Regression test: delta-mode admin story listing must exclude drafts.

`GET /admin/stories?updated_since=...` is used by the SWR cache to fetch
incremental updates. The non-delta path uses `_build_story_query()` which
excludes drafts by default, but the delta path was previously a separate
query that filtered only by `organization_id` + timestamp — leaking unsubmitted
drafts to reviewers.
"""
from datetime import datetime, timedelta

from app.models.story import Story
from app.utils.tz import now_ist


def test_delta_mode_excludes_draft_stories(client, db, reporter, auth_header):
    now = now_ist()

    draft = Story(
        id="story-draft",
        reporter_id=reporter.id,
        headline="Draft Headline",
        category="politics",
        paragraphs=[{"id": "p1", "text": "draft body"}],
        status="draft",
        organization_id="org-test",
        updated_at=now,
    )
    submitted = Story(
        id="story-submitted",
        reporter_id=reporter.id,
        headline="Submitted Headline",
        category="politics",
        paragraphs=[{"id": "p1", "text": "submitted body"}],
        status="submitted",
        organization_id="org-test",
        updated_at=now,
    )
    db.add_all([draft, submitted])
    db.commit()

    earlier = (now - timedelta(hours=1)).isoformat()
    resp = client.get(
        "/admin/stories",
        params={"updated_since": earlier},
        headers=auth_header,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = [s["id"] for s in body["stories"]]
    assert "story-submitted" in ids
    assert "story-draft" not in ids
