"""Helpers shared across edition sub-modules."""
from datetime import date as date_type, timedelta

from sqlalchemy.orm import Session

from ...models.edition import Edition, EditionPage
from ...models.org_config import OrgConfig


# How far ahead the canonical edition auto-seeder primes the calendar.
# The seeder runs lazily whenever someone lists editions for a date,
# so today + 6 = a one-week rolling window with no scheduled job.
CANONICAL_SEED_HORIZON_DAYS = 7

# Number of blank pages every freshly-seeded canonical edition gets
# (named "Page 1" … "Page N"). Independent of OrgConfig.page_suggestions
# — that preset is for free-form manual editions; canonical geographic
# editions all share the same uniform layout.
CANONICAL_EDITION_PAGE_COUNT = 20


PAPER_TYPE_LABELS = {
    "daily": "Daily",
    "weekend": "Weekend",
    "evening": "Evening",
    "special": "Special",
}


def _generate_title(publication_date, paper_type: str) -> str:
    label = PAPER_TYPE_LABELS.get(paper_type, paper_type.capitalize())
    return f"{label} - {publication_date.strftime('%d %b %Y')}"


def _edition_to_response(edition: Edition) -> dict:
    """Convert an Edition ORM object to a dict with computed counts."""
    page_count = len(edition.pages) if edition.pages else 0
    story_count = sum(
        len(p.story_assignments) for p in edition.pages
    ) if edition.pages else 0
    return {
        "id": edition.id,
        "publication_date": edition.publication_date,
        "paper_type": edition.paper_type,
        "title": edition.title,
        "status": edition.status,
        "page_count": page_count,
        "story_count": story_count,
        "created_at": edition.created_at,
        "updated_at": edition.updated_at,
    }


def seed_canonical_pages(
    db: Session,
    edition: Edition,
    count: int = CANONICAL_EDITION_PAGE_COUNT,
) -> None:
    """Add ``count`` blank pages named 'Page 1' … 'Page N' to a freshly
    auto-seeded canonical edition. No-op if pages already exist (so
    re-running the seeder doesn't duplicate). Caller controls the
    transaction.
    """
    if edition.pages:
        return
    for i in range(1, count + 1):
        db.add(
            EditionPage(
                edition_id=edition.id,
                page_number=i,
                page_name=f"Page {i}",
                sort_order=i,
            )
        )


def seed_default_pages(db: Session, edition: Edition, cfg: OrgConfig | None) -> None:
    """Add the org's preset daily pages (Front Page, Page 2, …) to a
    freshly-created Edition. Mirrors the inline logic in
    create_edition so manual and auto-seeded editions both land with
    the same default page set.

    No-ops if the edition already has pages or the org has no
    page_suggestions configured. Caller controls the transaction.
    """
    if edition.pages:
        return
    suggestions = (cfg.page_suggestions or []) if cfg else []
    active = [s for s in suggestions if s.get("is_active", True)]
    active.sort(key=lambda s: s.get("sort_order", 0))
    for idx, s in enumerate(active, start=1):
        db.add(
            EditionPage(
                edition_id=edition.id,
                page_number=idx,
                page_name=s.get("name") or f"Page {idx}",
                sort_order=idx,
            )
        )


def ensure_canonical_editions(
    db: Session,
    org_id: str,
    anchor_date: date_type,
    horizon_days: int = CANONICAL_SEED_HORIZON_DAYS,
) -> int:
    """Idempotently materialise the org's canonical editions for a rolling
    window starting at ``anchor_date``.

    For each day in [anchor_date, anchor_date + horizon_days) and each
    name in OrgConfig.edition_names, creates a daily Edition with
    ``title = name`` if no Edition with that exact title already exists
    for that date. Manual editions (different titles) are untouched.

    Triggered lazily from /admin/editions list calls so visiting the
    Page Arrangement screen keeps the window populated — no cron.

    Returns the count of newly-created Edition rows. Does NOT commit;
    caller controls the transaction.
    """
    cfg = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    names = (cfg.edition_names or []) if cfg else []
    # Strip blanks/dupes while preserving order so the seed list stays
    # predictable even if an admin pastes whitespace into the editor.
    seen = set()
    canonical = []
    for raw in names:
        if not isinstance(raw, str):
            continue
        name = raw.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        canonical.append(name)
    if not canonical:
        return 0

    dates = [anchor_date + timedelta(days=i) for i in range(horizon_days)]

    # Single bulk lookup (org, date, title) so we add only the missing
    # rows. Avoids a per-(date, name) round-trip — the matrix can hit
    # this on every date change, so the hot-path stays cheap.
    existing = (
        db.query(Edition.publication_date, Edition.title)
        .filter(
            Edition.organization_id == org_id,
            Edition.publication_date.in_(dates),
            Edition.title.in_(canonical),
        )
        .all()
    )
    existing_keys = {(d, t) for d, t in existing}

    created_editions: list[Edition] = []
    for d in dates:
        for name in canonical:
            if (d, name) in existing_keys:
                continue
            ed = Edition(
                organization_id=org_id,
                publication_date=d,
                paper_type="daily",
                title=name,
            )
            db.add(ed)
            created_editions.append(ed)
    if not created_editions:
        return 0

    # Flush so each new Edition gets its UUID before we attach pages.
    # Canonical editions get the uniform Page 1..N layout — they share
    # the same page structure across geographic editions, so we don't
    # use OrgConfig.page_suggestions here.
    db.flush()
    for ed in created_editions:
        seed_canonical_pages(db, ed)
    return len(created_editions)


def _page_to_response(page: EditionPage) -> dict:
    """Convert an EditionPage ORM object to a dict with computed counts."""
    story_count = len(page.story_assignments) if page.story_assignments else 0
    return {
        "id": page.id,
        "page_number": page.page_number,
        "page_name": page.page_name,
        "sort_order": page.sort_order,
        "story_count": story_count,
        "story_assignments": page.story_assignments,
    }
