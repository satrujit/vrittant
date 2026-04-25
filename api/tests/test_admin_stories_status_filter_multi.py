"""#56 — kanban board hides stories the moment they're marked layout_completed.

The kanban (BucketDetailPage) used to fetch ``GET /admin/stories?status=approved``
which excluded ``layout_completed``. Reviewers complained that stories were
"disappearing" from the board the instant a layout was marked complete, even
though the story is still part of the edition workflow (editors swap pages,
drag stories between editions, etc.) until publication.

Fix: ``status`` now accepts a comma-separated list — the kanban passes
``approved,layout_completed`` and both buckets show up. Single-value usage is
unchanged (existing callers don't break).
"""

from app.models.story import Story


def _seed_three_statuses(db) -> None:
    """One story per status: submitted, approved, layout_completed."""
    db.add_all(
        [
            Story(
                id="s-submitted",
                reporter_id="reporter-1",
                headline="Submitted story",
                category="politics",
                paragraphs=[{"id": "p1", "text": "x"}],
                status="submitted",
                organization_id="org-test",
            ),
            Story(
                id="s-approved",
                reporter_id="reporter-1",
                headline="Approved story",
                category="politics",
                paragraphs=[{"id": "p1", "text": "x"}],
                status="approved",
                organization_id="org-test",
            ),
            Story(
                id="s-layout",
                reporter_id="reporter-1",
                headline="Layout-complete story",
                category="politics",
                paragraphs=[{"id": "p1", "text": "x"}],
                status="layout_completed",
                organization_id="org-test",
            ),
        ]
    )
    db.commit()


def _ids(resp):
    return {s["id"] for s in resp.json()["stories"]}


def test_status_filter_accepts_single_value_unchanged(
    client, db, reviewer, reporter, override_user, auth_header
):
    """Existing callers that pass a single status keep working."""
    override_user(reviewer)
    _seed_three_statuses(db)
    resp = client.get(
        "/admin/stories", params={"status": "approved"}, headers=auth_header
    )
    assert resp.status_code == 200
    assert _ids(resp) == {"s-approved"}


def test_status_filter_accepts_comma_separated_list(
    client, db, reviewer, reporter, override_user, auth_header
):
    """Kanban passes ``approved,layout_completed`` — both must come back."""
    override_user(reviewer)
    _seed_three_statuses(db)
    resp = client.get(
        "/admin/stories",
        params={"status": "approved,layout_completed"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert _ids(resp) == {"s-approved", "s-layout"}, (
        "stories marked layout_completed must remain on the kanban alongside approved ones"
    )


def test_status_filter_tolerates_extra_whitespace(
    client, db, reviewer, reporter, override_user, auth_header
):
    """Defensive: a stray space after the comma shouldn't drop the second status."""
    override_user(reviewer)
    _seed_three_statuses(db)
    resp = client.get(
        "/admin/stories",
        params={"status": "approved , layout_completed"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert _ids(resp) == {"s-approved", "s-layout"}
