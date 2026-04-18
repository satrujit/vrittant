from app.models.story import Story


def test_story_has_assigned_to_column():
    s = Story(reporter_id="r", organization_id="o")
    assert hasattr(s, "assigned_to")


def test_story_has_assigned_match_reason_column():
    s = Story(reporter_id="r", organization_id="o")
    assert hasattr(s, "assigned_match_reason")
