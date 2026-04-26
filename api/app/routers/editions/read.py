"""Edition read endpoints: list, detail."""
from datetime import date as date_type, timedelta

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ...database import get_db
from ...deps import require_reviewer, get_current_org_id
from ...models.edition import Edition, EditionPage
from ...models.user import User
from ...schemas.edition import (
    EditionDetailResponse,
    EditionListResponse,
)
from ...utils.tz import now_ist
from . import router
from ._shared import _edition_to_response, _page_to_response, ensure_canonical_editions


def _edition_with_pages(edition: Edition) -> dict:
    """List-shape response: edition summary + nested pages."""
    resp = _edition_to_response(edition)
    sorted_pages = sorted(
        edition.pages or [],
        key=lambda p: (p.sort_order or 0, p.page_number or 0),
    )
    resp["pages"] = [_page_to_response(p) for p in sorted_pages]
    return resp


# ---------------------------------------------------------------------------
# GET /admin/editions
# ---------------------------------------------------------------------------

@router.get("", response_model=EditionListResponse)
def list_editions(
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    status_filter: str | None = Query(None, alias="status"),
    publication_date: date_type | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    base_filters = [Edition.organization_id == org_id]
    if status_filter:
        base_filters.append(Edition.status == status_filter)
    if publication_date is not None:
        base_filters.append(Edition.publication_date == publication_date)

    # Self-healing 7-day window. Two trigger paths:
    #   * Filtered list (placement matrix on a specific date) → anchor
    #     at that date so navigating forward stays primed.
    #   * Unfiltered list (BucketsListPage) → anchor at TOMORROW. The
    #     newspaper editorial convention is "today's work = tomorrow's
    #     paper", so today's date sits one slot behind the rolling
    #     canonical window. Manual editions for today/yesterday are
    #     left untouched.
    # Idempotent and cheap: bulk SELECT against the unique
    # (org, date, title) index before INSERT.
    try:
        if publication_date is not None:
            anchor = publication_date
        else:
            anchor = now_ist().date() + timedelta(days=1)
        created = ensure_canonical_editions(db, org_id, anchor)
        if created:
            db.commit()
    except Exception:
        # Never let auto-seed break a read. Worst case the table shows
        # the previously-existing editions; manual create still works.
        db.rollback()

    # Total count (without joins)
    total = db.query(func.count(Edition.id)).filter(*base_filters).scalar()

    # Fetch editions with eager-loaded pages and story assignments
    editions = (
        db.query(Edition)
        .filter(*base_filters)
        .options(
            joinedload(Edition.pages).joinedload(EditionPage.story_assignments)
        )
        .order_by(Edition.publication_date.desc(), Edition.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Deduplicate from joinedload (SQLAlchemy may return duplicates with joins)
    seen = set()
    unique_editions = []
    for e in editions:
        if e.id not in seen:
            seen.add(e.id)
            unique_editions.append(e)

    return EditionListResponse(
        editions=[_edition_with_pages(e) for e in unique_editions],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /admin/editions/{edition_id}
# ---------------------------------------------------------------------------

@router.get("/{edition_id}", response_model=EditionDetailResponse)
def get_edition(edition_id: str, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    edition = (
        db.query(Edition)
        .options(
            joinedload(Edition.pages).joinedload(EditionPage.story_assignments)
        )
        .filter(Edition.id == edition_id, Edition.organization_id == org_id)
        .first()
    )
    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Edition not found"
        )

    pages_data = [_page_to_response(p) for p in edition.pages]
    resp = _edition_to_response(edition)
    resp["pages"] = pages_data
    return resp
