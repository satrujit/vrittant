"""Tests for has_revision flag in story list."""


def test_list_stories_has_revision_flag(client, auth_header, sample_story, db):
    from app.models.story import Story

    # Create a second story (no revision)
    story2 = Story(
        id="story-2",
        reporter_id=sample_story.reporter_id,
        headline="Second Story",
        paragraphs=[],
        status="submitted",
        organization_id="org-test",
    )
    db.add(story2)
    db.commit()

    # Create revision on first story
    client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Edited", "paragraphs": []},
        headers=auth_header,
    )

    resp = client.get("/admin/stories", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()

    stories_by_id = {s["id"]: s for s in data["stories"]}
    assert stories_by_id[sample_story.id]["has_revision"] is True
    assert stories_by_id["story-2"]["has_revision"] is False
