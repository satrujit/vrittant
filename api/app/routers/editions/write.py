"""Edition write endpoints: create, update, delete, page CRUD, story assignment."""
from fastapi import Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ...database import get_db
from ...deps import require_reviewer, get_current_org_id
from ...utils.tz import now_ist
from ...models.edition import Edition, EditionPage, EditionPageStory
from ...models.org_config import OrgConfig
from ...models.story import Story
from ...models.user import User
from ...schemas.edition import (
    EditionCreate,
    EditionPageCreate,
    EditionPageResponse,
    EditionPageUpdate,
    EditionResponse,
    EditionUpdate,
    StoryAssignmentUpdate,
)
from ...utils.scope import get_owned_or_404
from . import router
from ._shared import _edition_to_response, _generate_title, _page_to_response, seed_default_pages


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
    db.flush()  # need edition.id before adding child pages

    # For "daily" editions, auto-seed pages from the org's master
    # page_suggestions preset so the reviewer doesn't have to add them
    # manually for every day. Other paper types (weekend / evening /
    # special) start blank — they're often custom layouts.
    if body.paper_type == "daily":
        cfg = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
        seed_default_pages(db, edition, cfg)

    db.commit()
    db.refresh(edition)
    return _edition_to_response(edition)


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

    edition.updated_at = now_ist()
    db.commit()
    db.refresh(edition)
    return _edition_to_response(edition)


# ---------------------------------------------------------------------------
# DELETE /admin/editions/{edition_id}
# ---------------------------------------------------------------------------

@router.delete("/{edition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_edition(edition_id: str, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    edition = get_owned_or_404(db, Edition, edition_id, org_id, entity_label="Edition")
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
    edition = get_owned_or_404(db, Edition, edition_id, org_id, entity_label="Edition")

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
    get_owned_or_404(db, Edition, edition_id, org_id, entity_label="Edition")

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
    get_owned_or_404(db, Edition, edition_id, org_id, entity_label="Edition")

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
    get_owned_or_404(db, Edition, edition_id, org_id, entity_label="Edition")

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

    # Security: every story_id MUST belong to this org. Without this check
    # any reviewer can attach foreign-org stories to their own edition page.
    # Loop the helper per-id (clearer than a bulk query + diff).
    if body.story_ids:
        for sid in body.story_ids:
            get_owned_or_404(db, Story, sid, org_id, entity_label="Story")

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


# ---------------------------------------------------------------------------
# POST /admin/editions/{edition_id}/pages/{page_id}/stories/{story_id}
# Append a single story to a page (used from ReviewPage)
# ---------------------------------------------------------------------------

@router.post(
    "/{edition_id}/pages/{page_id}/stories/{story_id}",
    status_code=status.HTTP_201_CREATED,
)
def add_story_to_page(
    edition_id: str,
    page_id: str,
    story_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    get_owned_or_404(db, Edition, edition_id, org_id, entity_label="Edition")

    page = db.query(EditionPage).filter(EditionPage.id == page_id, EditionPage.edition_id == edition_id).first()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    # Security: the story must belong to this org.
    get_owned_or_404(db, Story, story_id, org_id, entity_label="Story")

    # Check if already assigned to this page
    existing = db.query(EditionPageStory).filter(
        EditionPageStory.edition_page_id == page_id,
        EditionPageStory.story_id == story_id,
    ).first()
    if existing:
        return {"detail": "Already assigned"}

    max_order = (
        db.query(func.max(EditionPageStory.sort_order))
        .filter(EditionPageStory.edition_page_id == page_id)
        .scalar()
    ) or -1

    assignment = EditionPageStory(
        edition_page_id=page_id,
        story_id=story_id,
        sort_order=max_order + 1,
    )
    db.add(assignment)
    db.commit()
    return {"detail": "Assigned"}


# ---------------------------------------------------------------------------
# DELETE /admin/editions/{edition_id}/pages/{page_id}/stories/{story_id}
# Remove a single story from a page
# ---------------------------------------------------------------------------

@router.delete(
    "/{edition_id}/pages/{page_id}/stories/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_story_from_page(
    edition_id: str,
    page_id: str,
    story_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    get_owned_or_404(db, Edition, edition_id, org_id, entity_label="Edition")

    page = db.query(EditionPage).filter(EditionPage.id == page_id, EditionPage.edition_id == edition_id).first()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")

    deleted = db.query(EditionPageStory).filter(
        EditionPageStory.edition_page_id == page_id,
        EditionPageStory.story_id == story_id,
    ).delete()
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    db.commit()
