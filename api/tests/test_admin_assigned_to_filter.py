from app.models.story import Story
from app.models.user import User


def _mk_user(db, *, name, user_type="reviewer"):
    u = User(name=name, phone=name, user_type=user_type, area_name="",
             organization_id="org1", organization="Org",
             categories=[], regions=[], is_active=True)
    db.add(u); db.commit(); db.refresh(u)
    return u


def _mk_story(db, reporter_id, assignee_id, *, status="submitted"):
    s = Story(reporter_id=reporter_id, organization_id="org1",
              status=status, paragraphs=[], assigned_to=assignee_id)
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_filter_assigned_to_me(client, db, override_user):
    reporter = _mk_user(db, name="rep", user_type="reporter")
    me = _mk_user(db, name="me")
    other = _mk_user(db, name="other")
    s_mine = _mk_story(db, reporter.id, me.id)
    s_other = _mk_story(db, reporter.id, other.id)
    override_user(me)

    resp = client.get("/admin/stories?assigned_to=me")
    assert resp.status_code == 200, resp.text
    ids = [s["id"] for s in resp.json()["stories"]]
    assert s_mine.id in ids
    assert s_other.id not in ids


def test_filter_assigned_to_specific_user(client, db, override_user):
    reporter = _mk_user(db, name="rep2", user_type="reporter")
    me = _mk_user(db, name="me2")
    other = _mk_user(db, name="other2")
    s_other = _mk_story(db, reporter.id, other.id)
    override_user(me)

    resp = client.get(f"/admin/stories?assigned_to={other.id}")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()["stories"]]
    assert s_other.id in ids


def test_filter_omitted_returns_all(client, db, override_user):
    reporter = _mk_user(db, name="rep3", user_type="reporter")
    me = _mk_user(db, name="me3")
    other = _mk_user(db, name="other3")
    s_mine = _mk_story(db, reporter.id, me.id)
    s_other = _mk_story(db, reporter.id, other.id)
    override_user(me)

    resp = client.get("/admin/stories")
    ids = [s["id"] for s in resp.json()["stories"]]
    assert s_mine.id in ids
    assert s_other.id in ids
