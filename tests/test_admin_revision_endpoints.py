"""Tests for story revision upsert via PUT /admin/stories/{id}."""


def test_put_creates_revision_on_first_save(client, auth_header, sample_story, db):
    """First PUT should INSERT a new revision row."""
    resp = client.put(
        f"/admin/stories/{sample_story.id}",
        json={
            "headline": "Editor Headline",
            "paragraphs": [{"id": "p1", "text": "Editor text"}],
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Revision should be present in response
    assert data["revision"] is not None
    assert data["revision"]["headline"] == "Editor Headline"
    rev_paragraphs = data["revision"]["paragraphs"]
    assert len(rev_paragraphs) == 1
    assert rev_paragraphs[0]["id"] == "p1"
    assert rev_paragraphs[0]["text"] == "Editor text"

    # Original story should be unchanged
    assert data["headline"] == "Original Headline"
    assert data["paragraphs"] == [
        {"id": "p1", "text": "Original paragraph one."},
        {"id": "p2", "text": "Original paragraph two."},
    ]


def test_put_updates_existing_revision(client, auth_header, sample_story):
    """Second PUT should UPDATE the existing revision row, not create a new one."""
    # First save
    client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "First edit", "paragraphs": [{"id": "p1", "text": "v1"}]},
        headers=auth_header,
    )
    # Second save
    resp = client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Second edit", "paragraphs": [{"id": "p1", "text": "v2"}]},
        headers=auth_header,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["revision"]["headline"] == "Second edit"
    rev_paragraphs = data["revision"]["paragraphs"]
    assert len(rev_paragraphs) == 1
    assert rev_paragraphs[0]["id"] == "p1"
    assert rev_paragraphs[0]["text"] == "v2"


def test_put_story_not_found(client, auth_header):
    resp = client.put(
        "/admin/stories/nonexistent",
        json={"headline": "x", "paragraphs": []},
        headers=auth_header,
    )
    assert resp.status_code == 404


def test_put_preserves_original_story_immutably(client, auth_header, sample_story, db):
    """After PUT, stories table should remain unchanged."""
    from app.models.story import Story

    client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Totally new headline", "paragraphs": [{"id": "p1", "text": "new"}]},
        headers=auth_header,
    )

    db.expire_all()
    story = db.query(Story).filter(Story.id == sample_story.id).first()
    assert story.headline == "Original Headline"
    assert story.paragraphs == [
        {"id": "p1", "text": "Original paragraph one."},
        {"id": "p2", "text": "Original paragraph two."},
    ]


def test_save_layout_config(client, auth_header, sample_story):
    """PUT with layout_config should persist it on the revision."""
    layout = {
        "template_id": "tpl-1",
        "zones": [{"id": "z1", "type": "headline", "font_size_pt": 32}],
    }
    resp = client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Test", "layout_config": layout},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert resp.json()["revision"]["layout_config"] == layout
