"""Tests for GET /admin/stories/{id} with revision data."""


def test_get_story_without_revision(client, auth_header, sample_story):
    resp = client.get(f"/admin/stories/{sample_story.id}", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["revision"] is None
    assert data["headline"] == "Original Headline"


def test_get_story_with_revision(client, auth_header, sample_story):
    # Create a revision via PUT
    client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Edited", "paragraphs": [{"id": "p1", "text": "new"}]},
        headers=auth_header,
    )

    resp = client.get(f"/admin/stories/{sample_story.id}", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["revision"] is not None
    assert data["revision"]["headline"] == "Edited"
    # Original preserved
    assert data["headline"] == "Original Headline"
