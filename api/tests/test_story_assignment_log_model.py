from app.models.story_assignment_log import StoryAssignmentLog


def test_log_columns():
    log = StoryAssignmentLog(
        story_id="s", from_user_id=None, to_user_id="u",
        assigned_by=None, reason="auto",
    )
    assert log.story_id == "s"
    assert log.from_user_id is None
    assert log.to_user_id == "u"
    assert log.assigned_by is None
    assert log.reason == "auto"
