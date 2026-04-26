"""GET /admin/reporters must surface each user's categories and regions.

Regression: the org-admin "Edit user" modal pre-fills its scope
checkboxes from this endpoint's response. Before the fix, the
AdminReporterResponse schema lacked `categories` and `regions`
entirely, so Pydantic dropped them — the modal always opened
unchecked even when the DB held real values, making it look like
edits weren't being saved (they were; the read just couldn't see
them).
"""
from app.models.user import User


def _make_reviewer(db, *, categories, regions):
    u = User(
        id="rev-scoped",
        name="Scoped Reviewer",
        phone="+919999999999",
        user_type="reviewer",
        organization="Test Org",
        organization_id="org-test",
        is_active=True,
        categories=categories,
        regions=regions,
    )
    db.add(u)
    db.commit()
    return u


def test_reporters_list_returns_categories_and_regions(
    client, db, reviewer, override_user, auth_header
):
    _make_reviewer(
        db,
        categories=["politics", "crime"],
        regions=["Bhubaneswar", "Cuttack"],
    )
    override_user(reviewer)

    resp = client.get("/admin/reporters", headers=auth_header)
    assert resp.status_code == 200

    by_id = {r["id"]: r for r in resp.json()["reporters"]}
    scoped = by_id["rev-scoped"]
    assert scoped["categories"] == ["politics", "crime"]
    assert scoped["regions"] == ["Bhubaneswar", "Cuttack"]


def test_reporters_list_returns_empty_lists_for_users_without_scope(
    client, db, reviewer, reporter, override_user, auth_header
):
    """Reporters and unscoped reviewers must come back with empty
    arrays (not null, not missing) — the frontend assumes Array.isArray
    when initialising the form."""
    override_user(reviewer)

    resp = client.get("/admin/reporters", headers=auth_header)
    assert resp.status_code == 200

    for r in resp.json()["reporters"]:
        assert r["categories"] == []
        assert r["regions"] == []
