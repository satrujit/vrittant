"""Unit tests for pick_assignee — three-step funnel + tie-breaking."""
import pytest

from app.models.story import Story
from app.models.user import User
from app.services.assignment import pick_assignee, NoReviewersAvailable


def _make_user(db, *, name, user_type="reviewer", area="", categories=None, regions=None, active=True):
    u = User(
        name=name, phone=name, user_type=user_type, area_name=area,
        organization_id="org1", organization="Org",
        categories=categories or [], regions=regions or [], is_active=active,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_story(db, *, reporter, category=None):
    s = Story(reporter_id=reporter.id, organization_id="org1", category=category, paragraphs=[])
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_category_match_picks_only_matching_reviewer(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="Koraput")
    sports = _make_user(db, name="sportsr", categories=["sports"])
    _politics = _make_user(db, name="politicsr", categories=["politics"])
    story = _make_story(db, reporter=reporter, category="sports")

    user, reason = pick_assignee(story, db)
    assert user.id == sports.id
    assert reason == "category"


def test_category_match_least_loaded_among_candidates(db):
    reporter = _make_user(db, name="rep", user_type="reporter")
    a = _make_user(db, name="a", categories=["sports"])
    b = _make_user(db, name="b", categories=["sports"])
    db.add(Story(reporter_id=reporter.id, organization_id="org1",
                 assigned_to=a.id, status="submitted", paragraphs=[]))
    db.commit()
    story = _make_story(db, reporter=reporter, category="sports")

    user, _ = pick_assignee(story, db)
    assert user.id == b.id


def test_general_category_skips_step_1(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="Koraput")
    _make_user(db, name="sportsr", categories=["sports"])
    region_match = _make_user(db, name="kor", regions=["Koraput"])
    story = _make_story(db, reporter=reporter, category="general")

    user, reason = pick_assignee(story, db)
    assert user.id == region_match.id
    assert reason == "region"


def test_null_category_skips_step_1(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="Koraput")
    region_match = _make_user(db, name="kor", regions=["Koraput"])
    story = _make_story(db, reporter=reporter, category=None)

    user, reason = pick_assignee(story, db)
    assert user.id == region_match.id
    assert reason == "region"


def test_region_match_normalized(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="  KORAPUT District ")
    region_match = _make_user(db, name="kor", regions=["koraput"])
    story = _make_story(db, reporter=reporter)

    user, reason = pick_assignee(story, db)
    assert user.id == region_match.id
    assert reason == "region"


def test_overall_fallback_when_no_match(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="Cuttack")
    a = _make_user(db, name="a", categories=["politics"])
    b = _make_user(db, name="b", regions=["Bhubaneswar"])
    story = _make_story(db, reporter=reporter, category="sports")

    user, reason = pick_assignee(story, db)
    assert user.id in (a.id, b.id)
    assert reason == "load_balance"


def test_inactive_reviewer_excluded(db):
    reporter = _make_user(db, name="rep", user_type="reporter")
    _inactive = _make_user(db, name="i", categories=["sports"], active=False)
    active = _make_user(db, name="a", categories=["sports"])
    story = _make_story(db, reporter=reporter, category="sports")

    user, _ = pick_assignee(story, db)
    assert user.id == active.id


def test_no_reviewers_raises(db):
    reporter = _make_user(db, name="rep", user_type="reporter")
    story = _make_story(db, reporter=reporter, category="sports")

    with pytest.raises(NoReviewersAvailable):
        pick_assignee(story, db)


def test_tie_breaks_on_lowest_user_id(db):
    reporter = _make_user(db, name="rep", user_type="reporter")
    a = _make_user(db, name="a", categories=["sports"])
    b = _make_user(db, name="b", categories=["sports"])
    expected_id = min(a.id, b.id)
    story = _make_story(db, reporter=reporter, category="sports")

    user, _ = pick_assignee(story, db)
    assert user.id == expected_id
