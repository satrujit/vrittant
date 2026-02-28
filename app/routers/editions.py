from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import require_reviewer, get_current_org_id
from ..models.edition import Edition, EditionPage, EditionPageStory
from ..models.user import User
from ..schemas.edition import (
    EditionCreate,
    EditionDetailResponse,
    EditionListResponse,
    EditionPageCreate,
    EditionPageResponse,
    EditionPageUpdate,
    EditionResponse,
    EditionUpdate,
    StoryAssignmentUpdate,
)

router = APIRouter(prefix="/admin/editions", tags=["editions"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# POST /admin/editions
# ---------------------------------------------------------------------------

@router.post("", response_model=EditionResponse, status_code=status.HTTP_201_CREATED)
def create_edition(body: EditionCreate, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    title = body.title if body.title else _generate_title(body.publication_date, body.paper_type)
    edition = Edition(
        publication_date=body.publication_date,
        paper_type=body.paper_type,
        title=title,
        organization_id=org_id,
    )
    db.add(edition)
    db.commit()
    db.refresh(edition)
    return _edition_to_response(edition)


# ---------------------------------------------------------------------------
# GET /admin/editions
# ---------------------------------------------------------------------------

@router.get("", response_model=EditionListResponse)
def list_editions(
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    # Total count (without joins)
    total = db.query(func.count(Edition.id)).filter(Edition.organization_id == org_id).scalar()

    # Fetch editions with eager-loaded pages and story assignments
    editions = (
        db.query(Edition)
        .filter(Edition.organization_id == org_id)
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
        editions=[_edition_to_response(e) for e in unique_editions],
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


# ---------------------------------------------------------------------------
# PUT /admin/editions/{edition_id}
# ---------------------------------------------------------------------------

@router.put("/{edition_id}", response_model=EditionResponse)
def update_edition(
    edition_id: str,
    body: EditionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
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

    if body.status is not None:
        allowed = {"draft", "finalized", "published"}
        if body.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(sorted(allowed))}",
            )
        edition.status = body.status

    if body.publication_date is not None:
        edition.publication_date = body.publication_date

    if body.paper_type is not None:
        allowed_types = {"daily", "weekend", "evening", "special"}
        if body.paper_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid paper_type. Must be one of: {', '.join(sorted(allowed_types))}",
            )
        edition.paper_type = body.paper_type

    if body.title is not None:
        edition.title = body.title

    # Auto-regenerate title when date or paper_type changes (unless a custom title was also provided)
    if (body.publication_date is not None or body.paper_type is not None) and body.title is None:
        edition.title = _generate_title(edition.publication_date, edition.paper_type)

    edition.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(edition)
    return _edition_to_response(edition)


# ---------------------------------------------------------------------------
# DELETE /admin/editions/{edition_id}
# ---------------------------------------------------------------------------

@router.delete("/{edition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_edition(edition_id: str, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    edition = db.query(Edition).filter(Edition.id == edition_id, Edition.organization_id == org_id).first()
    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Edition not found"
        )
    db.delete(edition)
    db.commit()


# ---------------------------------------------------------------------------
# POST /admin/editions/{edition_id}/pages
# ---------------------------------------------------------------------------

@router.post(
    "/{edition_id}/pages",
    response_model=EditionPageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_page(
    edition_id: str,
    body: EditionPageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    edition = db.query(Edition).filter(Edition.id == edition_id, Edition.organization_id == org_id).first()
    if not edition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Edition not found"
        )

    # Auto page_number = max existing + 1 if not provided
    if body.page_number is not None:
        page_number = body.page_number
    else:
        max_page = (
            db.query(func.max(EditionPage.page_number))
            .filter(EditionPage.edition_id == edition_id)
            .scalar()
        )
        page_number = (max_page or 0) + 1

    page = EditionPage(
        edition_id=edition_id,
        page_number=page_number,
        page_name=body.page_name,
        sort_order=page_number,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    return _page_to_response(page)


# ---------------------------------------------------------------------------
# PUT /admin/editions/{edition_id}/pages/{page_id}
# ---------------------------------------------------------------------------

@router.put(
    "/{edition_id}/pages/{page_id}",
    response_model=EditionPageResponse,
)
def update_page(
    edition_id: str,
    page_id: str,
    body: EditionPageUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    # Verify the edition belongs to this organization
    edition = db.query(Edition).filter(Edition.id == edition_id, Edition.organization_id == org_id).first()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edition not found")

    page = (
        db.query(EditionPage)
        .options(joinedload(EditionPage.story_assignments))
        .filter(
            EditionPage.id == page_id,
            EditionPage.edition_id == edition_id,
        )
        .first()
    )
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Page not found"
        )

    if body.page_name is not None:
        page.page_name = body.page_name
    if body.sort_order is not None:
        page.sort_order = body.sort_order

    db.commit()
    db.refresh(page)
    return _page_to_response(page)


# ---------------------------------------------------------------------------
# DELETE /admin/editions/{edition_id}/pages/{page_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{edition_id}/pages/{page_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_page(edition_id: str, page_id: str, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    # Verify the edition belongs to this organization
    edition = db.query(Edition).filter(Edition.id == edition_id, Edition.organization_id == org_id).first()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edition not found")

    page = (
        db.query(EditionPage)
        .filter(
            EditionPage.id == page_id,
            EditionPage.edition_id == edition_id,
        )
        .first()
    )
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Page not found"
        )
    db.delete(page)
    db.commit()


# ---------------------------------------------------------------------------
# PUT /admin/editions/{edition_id}/pages/{page_id}/stories
# ---------------------------------------------------------------------------

@router.put(
    "/{edition_id}/pages/{page_id}/stories",
    response_model=EditionPageResponse,
)
def assign_stories(
    edition_id: str,
    page_id: str,
    body: StoryAssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    # Verify the edition belongs to this organization
    edition = db.query(Edition).filter(Edition.id == edition_id, Edition.organization_id == org_id).first()
    if not edition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edition not found")

    page = (
        db.query(EditionPage)
        .options(joinedload(EditionPage.story_assignments))
        .filter(
            EditionPage.id == page_id,
            EditionPage.edition_id == edition_id,
        )
        .first()
    )
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Page not found"
        )

    # Delete existing assignments
    db.query(EditionPageStory).filter(
        EditionPageStory.edition_page_id == page_id
    ).delete()

    # Create new assignments in order
    for idx, story_id in enumerate(body.story_ids):
        assignment = EditionPageStory(
            edition_page_id=page_id,
            story_id=story_id,
            sort_order=idx,
        )
        db.add(assignment)

    db.commit()

    # Re-fetch page with fresh assignments
    page = (
        db.query(EditionPage)
        .options(joinedload(EditionPage.story_assignments))
        .filter(EditionPage.id == page_id)
        .first()
    )
    return _page_to_response(page)
