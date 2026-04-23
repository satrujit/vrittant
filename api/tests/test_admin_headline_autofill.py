"""Tests for headline auto-fill behavior in PUT /admin/stories/{id}.

Empty / blank headlines used to surface as visually-empty rows in the
list view. The PUT endpoint now derives a headline from the first body
paragraph when one isn't supplied (or only whitespace is supplied),
matching the behavior of the WhatsApp inbound webhook.
"""

import pytest

from app.models.story import Story


@pytest.fixture()
def editor_created_story(db, reporter):
    """A blank editor-created story (matches the create_blank_story shape)."""
    story = Story(
        id="story-editor-blank",
        reporter_id=reporter.id,
        headline="",
        paragraphs=[],
        status="submitted",
        organization_id="org-test",
        source="Editor Created",
    )
    db.add(story)
    db.commit()
    return story


def test_put_derives_headline_from_first_paragraph_when_blank(
    client, auth_header, editor_created_story, db
):
    """Empty submitted headline → first body line becomes headline."""
    resp = client.put(
        f"/admin/stories/{editor_created_story.id}",
        json={
            "headline": "",
            "paragraphs": [
                {"id": "p1", "text": "Cuttack heavy rain disrupts daily life."},
                {"id": "p2", "text": "Officials warn of more rainfall ahead."},
            ],
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    db.expire_all()
    story = db.query(Story).filter(Story.id == editor_created_story.id).first()
    assert story.headline == "Cuttack heavy rain disrupts daily life."


def test_put_derives_headline_from_first_line_only(
    client, auth_header, editor_created_story, db
):
    """Multi-line first paragraph → only first line is used."""
    resp = client.put(
        f"/admin/stories/{editor_created_story.id}",
        json={
            "headline": "   ",
            "paragraphs": [
                {"id": "p1", "text": "Headline-worthy first line.\nSecond line of body."},
            ],
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    db.expire_all()
    story = db.query(Story).filter(Story.id == editor_created_story.id).first()
    assert story.headline == "Headline-worthy first line."


def test_put_truncates_long_derived_headline(
    client, auth_header, editor_created_story, db
):
    """Derived headline > 120 chars is truncated with an ellipsis."""
    long_text = "a" * 200
    resp = client.put(
        f"/admin/stories/{editor_created_story.id}",
        json={
            "headline": "",
            "paragraphs": [{"id": "p1", "text": long_text}],
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    db.expire_all()
    story = db.query(Story).filter(Story.id == editor_created_story.id).first()
    assert len(story.headline) == 120
    assert story.headline.endswith("…")


def test_put_keeps_explicit_headline_over_body(
    client, auth_header, editor_created_story, db
):
    """Real headline submitted → body never overrides it."""
    resp = client.put(
        f"/admin/stories/{editor_created_story.id}",
        json={
            "headline": "User-chosen Headline",
            "paragraphs": [{"id": "p1", "text": "Body should not become headline."}],
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    db.expire_all()
    story = db.query(Story).filter(Story.id == editor_created_story.id).first()
    assert story.headline == "User-chosen Headline"


def test_put_skips_empty_paragraphs_when_deriving(
    client, auth_header, editor_created_story, db
):
    """Leading empty paragraphs are skipped — first non-empty wins."""
    resp = client.put(
        f"/admin/stories/{editor_created_story.id}",
        json={
            "headline": "",
            "paragraphs": [
                {"id": "p1", "text": ""},
                {"id": "p2", "text": "   "},
                {"id": "p3", "text": "Real first paragraph."},
            ],
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    db.expire_all()
    story = db.query(Story).filter(Story.id == editor_created_story.id).first()
    assert story.headline == "Real first paragraph."
