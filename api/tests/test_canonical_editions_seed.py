"""Auto-seed canonical editions over a 7-day rolling window.

Driven by OrgConfig.edition_names. The list endpoint primes the
calendar lazily on every visit:

  * `GET /admin/editions?publication_date=D`  → anchor = D
  * `GET /admin/editions`                     → anchor = today + 1
    (newspaper convention: today's editorial work = tomorrow's paper)

What we guarantee:
  * Visiting any date materialises the canonical 6 names × 7 days.
  * Re-visiting (same date) does NOT duplicate — idempotent.
  * Manual editions with non-canonical titles are untouched.
  * No edition_names configured → no auto-seeding (feature off).
  * Listing without a date filter still seeds (anchored at tomorrow).
"""
from datetime import date, timedelta
from unittest.mock import patch

from app.models.edition import Edition, EditionPage
from app.models.org_config import OrgConfig
from app.routers.editions._shared import CANONICAL_EDITION_PAGE_COUNT


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


def test_each_canonical_edition_gets_20_pages_named_page_n(
    client, db, reviewer, override_user, auth_header
):
    """Canonical geographic editions share a uniform layout — every
    auto-seeded edition lands with 'Page 1' … 'Page 20', independent
    of the org's free-form page_suggestions preset."""
    _seed_org_config(db)
    override_user(reviewer)
    anchor = date(2026, 5, 1)

    client.get(f"/admin/editions?publication_date={anchor.isoformat()}", headers=auth_header)

    sample = (
        db.query(Edition)
        .filter(
            Edition.organization_id == "org-test",
            Edition.publication_date == anchor,
            Edition.title == "Bhubaneswar",
        )
        .first()
    )
    pages = (
        db.query(EditionPage)
        .filter(EditionPage.edition_id == sample.id)
        .order_by(EditionPage.sort_order)
        .all()
    )
    assert len(pages) == CANONICAL_EDITION_PAGE_COUNT == 20
    assert [p.page_name for p in pages] == [f"Page {i}" for i in range(1, 21)]
    assert [p.page_number for p in pages] == list(range(1, 21))


def test_unfiltered_list_seeds_at_tomorrow(
    client, db, reviewer, override_user, auth_header
):
    """The buckets list page calls /admin/editions with no date filter.
    It still has to trigger the seeder — anchored at *tomorrow* — so
    the canonical editions appear in the Page Arrangement table."""
    _seed_org_config(db)
    override_user(reviewer)

    # Pin "now" so the assertion is deterministic. Patches the symbol
    # imported inside the read module, not the source utility.
    from datetime import datetime, timezone, timedelta as td

    fake_now = datetime(2026, 4, 26, 10, 0, tzinfo=timezone(td(hours=5, minutes=30)))
    with patch("app.routers.editions.read.now_ist", return_value=fake_now):
        resp = client.get("/admin/editions", headers=auth_header)
        assert resp.status_code == 200

    tomorrow = date(2026, 4, 27)

    # Today (26 Apr) must NOT be auto-seeded — it's a slot for manual
    # editions only under the today+1 convention.
    today_count = (
        db.query(Edition)
        .filter(Edition.organization_id == "org-test", Edition.publication_date == date(2026, 4, 26))
        .count()
    )
    assert today_count == 0

    # Tomorrow + the next 6 days must each have all 6 canonical names.
    for offset in range(7):
        d = tomorrow + timedelta(days=offset)
        titles = sorted(
            r.title
            for r in db.query(Edition)
            .filter(Edition.organization_id == "org-test", Edition.publication_date == d)
            .all()
        )
        assert titles == sorted(CANONICAL), f"Day {d}: got {titles}"
