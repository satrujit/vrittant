"""Auto-seed canonical editions over a 7-day rolling window.

Driven by OrgConfig.edition_names. The list endpoint
(`GET /admin/editions?publication_date=…`) primes the calendar lazily
on every visit, so reviewers always find the geographic edition rows
ready in Page Arrangement.

What we guarantee:
  * Visiting any date materialises the canonical 6 names × 7 days.
  * Re-visiting (same date) does NOT duplicate — idempotent.
  * Manual editions with non-canonical titles are untouched.
  * No edition_names configured → no auto-seeding (feature off).
"""
from datetime import date, timedelta

from app.models.edition import Edition
from app.models.org_config import OrgConfig


CANONICAL = [
    "Bhubaneswar",
    "Central Odisha",
    "Coastal Odisha",
    "Balasore-Keonjhar",
    "Sambalpur",
    "Bhawanipatna",
]


def _seed_org_config(db, names=CANONICAL):
    db.add(
        OrgConfig(
            id="cfg-test",
            organization_id="org-test",
            categories=[],
            publication_types=[],
            page_suggestions=[],
            priority_levels=[],
            edition_schedule=[],
            edition_names=names,
        )
    )
    db.commit()


def test_first_visit_seeds_six_editions_for_seven_days(
    client, db, reviewer, override_user, auth_header
):
    _seed_org_config(db)
    override_user(reviewer)
    anchor = date(2026, 5, 1)

    resp = client.get(f"/admin/editions?publication_date={anchor.isoformat()}", headers=auth_header)
    assert resp.status_code == 200

    # All 6 canonical names should now exist for the requested date AND
    # the next 6 — that's the whole rolling window.
    for offset in range(7):
        d = anchor + timedelta(days=offset)
        rows = (
            db.query(Edition)
            .filter(Edition.organization_id == "org-test", Edition.publication_date == d)
            .all()
        )
        titles = sorted(r.title for r in rows)
        assert titles == sorted(CANONICAL), f"Day {d}: got {titles}"


def test_revisiting_same_date_is_idempotent(
    client, db, reviewer, override_user, auth_header
):
    _seed_org_config(db)
    override_user(reviewer)
    anchor = date(2026, 5, 1)

    client.get(f"/admin/editions?publication_date={anchor.isoformat()}", headers=auth_header)
    first_count = db.query(Edition).filter(Edition.organization_id == "org-test").count()

    client.get(f"/admin/editions?publication_date={anchor.isoformat()}", headers=auth_header)
    second_count = db.query(Edition).filter(Edition.organization_id == "org-test").count()

    assert first_count == 6 * 7
    assert second_count == first_count, "second visit must not create duplicates"


def test_manual_edition_with_custom_title_is_preserved(
    client, db, reviewer, override_user, auth_header
):
    _seed_org_config(db)
    override_user(reviewer)
    anchor = date(2026, 5, 1)

    # Pre-existing manual edition with a name that isn't in the canonical list.
    db.add(
        Edition(
            id="manual-1",
            organization_id="org-test",
            publication_date=anchor,
            paper_type="special",
            title="Pull-out Magazine",
        )
    )
    db.commit()

    client.get(f"/admin/editions?publication_date={anchor.isoformat()}", headers=auth_header)

    rows = (
        db.query(Edition)
        .filter(Edition.organization_id == "org-test", Edition.publication_date == anchor)
        .all()
    )
    titles = sorted(r.title for r in rows)
    # 6 canonical + 1 manual.
    assert titles == sorted(CANONICAL + ["Pull-out Magazine"])


def test_manual_edition_with_canonical_title_is_not_duplicated(
    client, db, reviewer, override_user, auth_header
):
    """If an org-admin pre-creates 'Bhubaneswar' manually, the auto-seeder
    must skip that (date, title) pair instead of erroring on the unique
    constraint or shadowing the manual row."""
    _seed_org_config(db)
    override_user(reviewer)
    anchor = date(2026, 5, 1)

    db.add(
        Edition(
            id="manual-bbsr",
            organization_id="org-test",
            publication_date=anchor,
            paper_type="daily",
            title="Bhubaneswar",
        )
    )
    db.commit()

    resp = client.get(f"/admin/editions?publication_date={anchor.isoformat()}", headers=auth_header)
    assert resp.status_code == 200

    bbsr = (
        db.query(Edition)
        .filter(
            Edition.organization_id == "org-test",
            Edition.publication_date == anchor,
            Edition.title == "Bhubaneswar",
        )
        .all()
    )
    assert len(bbsr) == 1
    assert bbsr[0].id == "manual-bbsr", "must reuse the pre-existing manual row"


def test_no_edition_names_configured_means_no_auto_seed(
    client, db, reviewer, override_user, auth_header
):
    _seed_org_config(db, names=[])
    override_user(reviewer)
    anchor = date(2026, 5, 1)

    resp = client.get(f"/admin/editions?publication_date={anchor.isoformat()}", headers=auth_header)
    assert resp.status_code == 200

    count = db.query(Edition).filter(Edition.organization_id == "org-test").count()
    assert count == 0
