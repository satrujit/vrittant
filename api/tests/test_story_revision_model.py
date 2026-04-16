import pytest
from sqlalchemy.exc import IntegrityError

from app.models.story_revision import StoryRevision


def test_create_story_revision(db, sample_story, reviewer):
    revision = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Edited Headline",
        paragraphs=[{"id": "p1", "text": "Edited paragraph."}],
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)

    assert revision.id is not None
    assert revision.story_id == sample_story.id
    assert revision.editor_id == reviewer.id
    assert revision.headline == "Edited Headline"
    assert revision.paragraphs == [{"id": "p1", "text": "Edited paragraph."}]
    assert revision.created_at is not None
    assert revision.updated_at is not None


def test_unique_constraint_one_revision_per_story(db, sample_story, reviewer):
    r1 = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="First edit",
        paragraphs=[],
    )
    db.add(r1)
    db.commit()

    r2 = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Second edit",
        paragraphs=[],
    )
    db.add(r2)
    with pytest.raises(IntegrityError):
        db.commit()


def test_revision_story_relationship(db, sample_story, reviewer):
    revision = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Edited",
        paragraphs=[],
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)

    assert revision.story is not None
    assert revision.story.id == sample_story.id
    assert revision.editor is not None
    assert revision.editor.id == reviewer.id


def test_revision_layout_config(db, sample_story, reviewer):
    from app.models.story_revision import StoryRevision

    rev = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Test",
        paragraphs=[],
        layout_config={
            "template_id": "tpl-1",
            "zones": [{"id": "z1", "type": "headline", "font_size_pt": 32}],
        },
    )
    db.add(rev)
    db.commit()
    db.refresh(rev)

    assert rev.layout_config is not None
    assert rev.layout_config["template_id"] == "tpl-1"


def test_revision_layout_config_defaults_to_none(db, sample_story, reviewer):
    from app.models.story_revision import StoryRevision

    rev = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Test",
        paragraphs=[],
    )
    db.add(rev)
    db.commit()
    db.refresh(rev)

    assert rev.layout_config is None
