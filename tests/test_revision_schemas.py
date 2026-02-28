from app.schemas.story import RevisionResponse


def test_revision_response_schema():
    data = {
        "id": "rev-1",
        "story_id": "story-1",
        "editor_id": "reviewer-1",
        "headline": "Edited",
        "paragraphs": [{"id": "p1", "text": "edited text"}],
        "created_at": "2026-02-28T10:00:00",
        "updated_at": "2026-02-28T10:00:00",
    }
    r = RevisionResponse(**data)
    assert r.id == "rev-1"
    assert r.headline == "Edited"
    assert len(r.paragraphs) == 1
