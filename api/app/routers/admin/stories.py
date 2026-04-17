"""Admin story endpoints: list, get, update, status, delete, image upload."""
import os
import uuid as uuid_mod
from datetime import datetime
from typing import Optional

from fastapi import Depends, File as FastAPIFile, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ...database import get_db
from ...deps import get_current_org_id, require_org_admin, require_reviewer
from ...models.story import Story
from ...models.story_revision import StoryRevision
from ...models.user import User
from ...utils.tz import now_ist
from . import router
from ._shared import (
    AdminStoryListItem,
    AdminStoryListResponse,
    AdminStoryResponse,
    AdminStoryUpdate,
    AdminStoryWithRevisionResponse,
    StatusUpdate,
    _build_story_query,
    _get_edition_info,
)


# ---------------------------------------------------------------------------
# GET /admin/stories
# ---------------------------------------------------------------------------

@router.get("/stories", response_model=AdminStoryListResponse)
def admin_list_stories(
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    status_filter: Optional[str] = Query(None, alias="status"),
    exclude_status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    reporter_id: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    recent: bool = Query(False),
    available_for_edition: Optional[str] = Query(None),
    updated_since: Optional[str] = Query(None, description="ISO timestamp — return only stories updated after this time"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    # --- Delta mode: return stories changed or soft-deleted since timestamp ---
    if updated_since:
        try:
            dt = datetime.fromisoformat(updated_since)
        except (ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid updated_since timestamp")

        delta_query = (
            db.query(Story)
            .options(joinedload(Story.reporter), joinedload(Story.revision))
            .filter(
                Story.organization_id == org_id,
                or_(Story.updated_at >= dt, Story.deleted_at >= dt),
            )
        )
        if reporter_id:
            delta_query = delta_query.filter(Story.reporter_id == reporter_id)

        # total = count of ALL non-deleted stories (so frontend can detect deletions)
        total = (
            db.query(Story)
            .filter(Story.organization_id == org_id, Story.deleted_at.is_(None), Story.status != "draft")
            .count()
        )

        stories = (
            delta_query.order_by(Story.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            AdminStoryListItem(
                id=s.id,
                reporter_id=s.reporter_id,
                headline=s.headline,
                category=s.category,
                location=s.location,
                source=s.source,
                paragraphs=s.paragraphs,
                status=s.status,
                submitted_at=s.submitted_at,
                created_at=s.created_at,
                updated_at=s.updated_at,
                reporter=s.reporter,
                has_revision=s.revision is not None,
                is_deleted=s.deleted_at is not None,
            )
            for s in stories
        ]

        return AdminStoryListResponse(stories=items, total=total)

    # --- Normal mode (no updated_since) ---
    query = _build_story_query(
        db,
        org_id=org_id,
        reporter_id=reporter_id,
        status_filter=status_filter,
        exclude_status=exclude_status,
        category=category,
        search=search,
        location=location,
        date_from=date_from,
        date_to=date_to,
        recent=recent,
        available_for_edition=available_for_edition,
    )

    total = query.count()
    stories = (
        query.options(joinedload(Story.revision))
        .order_by(Story.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        AdminStoryListItem(
            id=s.id,
            reporter_id=s.reporter_id,
            headline=s.headline,
            category=s.category,
            location=s.location,
            source=s.source,
            paragraphs=s.paragraphs,
            status=s.status,
            submitted_at=s.submitted_at,
            created_at=s.created_at,
            updated_at=s.updated_at,
            reporter=s.reporter,
            has_revision=s.revision is not None,
        )
        for s in stories
    ]

    return AdminStoryListResponse(stories=items, total=total)


# ---------------------------------------------------------------------------
# POST /admin/stories/create-blank  (editor creates new story from scratch)
# ---------------------------------------------------------------------------

class CreateBlankStoryResponse(BaseModel):
    story_id: str


@router.post("/stories/create-blank", response_model=CreateBlankStoryResponse)
def create_blank_story(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    now = now_ist()
    story = Story(
        id=str(uuid_mod.uuid4()),
        reporter_id=current_user.id,
        organization_id=org_id,
        headline="",
        paragraphs=[],
        status="draft",
        source="Editor Created",
        created_at=now,
        updated_at=now,
    )
    story.refresh_search_text()
    db.add(story)
    db.commit()
    return CreateBlankStoryResponse(story_id=story.id)


# ---------------------------------------------------------------------------
# GET /admin/stories/{story_id}
# ---------------------------------------------------------------------------

@router.get("/stories/{story_id}", response_model=AdminStoryWithRevisionResponse)
def admin_get_story(story_id: str, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    story = (
        db.query(Story)
        .options(joinedload(Story.reporter), joinedload(Story.revision))
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )
    # Build response with edition info
    resp = AdminStoryWithRevisionResponse.model_validate(story)
    resp.edition_info = _get_edition_info(db, story_id)
    return resp


# ---------------------------------------------------------------------------
# PUT /admin/stories/{story_id}/status
# ---------------------------------------------------------------------------

@router.put("/stories/{story_id}/status", response_model=AdminStoryResponse)
def admin_update_story_status(
    story_id: str,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    allowed = {"approved", "rejected", "published", "in_progress"}
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(allowed))}",
        )

    story = (
        db.query(Story)
        .options(joinedload(Story.reporter))
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )

    # Edition assignment is optional — approval no longer requires it
    story.status = body.status
    story.updated_at = now_ist()
    db.commit()
    db.refresh(story)
    return story


# ---------------------------------------------------------------------------
# PUT /admin/stories/{story_id}  (editor content update)
# ---------------------------------------------------------------------------

@router.put("/stories/{story_id}", response_model=AdminStoryWithRevisionResponse)
def admin_update_story(
    story_id: str,
    body: AdminStoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    story = (
        db.query(Story)
        .options(joinedload(Story.reporter), joinedload(Story.revision))
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )

    # Build revision data from request body
    rev_paragraphs = (
        [p.model_dump() for p in body.paragraphs]
        if body.paragraphs is not None
        else None
    )

    # Upsert: update existing revision or create new one
    existing_rev = story.revision
    if existing_rev:
        # Only overwrite fields that were explicitly provided
        if body.headline is not None:
            existing_rev.headline = body.headline
        if rev_paragraphs is not None:
            existing_rev.paragraphs = rev_paragraphs
        if body.layout_config is not None:
            existing_rev.layout_config = body.layout_config
        if body.english_translation is not None:
            existing_rev.english_translation = body.english_translation
        if body.social_posts is not None:
            existing_rev.social_posts = body.social_posts
        existing_rev.updated_at = now_ist()
    else:
        new_rev = StoryRevision(
            story_id=story.id,
            editor_id=current_user.id,
            headline=body.headline or story.headline,
            paragraphs=rev_paragraphs or story.paragraphs,
            layout_config=body.layout_config,
            english_translation=body.english_translation,
            social_posts=body.social_posts,
        )
        db.add(new_rev)

    # Update category on the story if provided (category is story-level, not content)
    if body.category is not None:
        story.category = body.category
    if body.priority is not None:
        story.priority = body.priority

    story.updated_at = now_ist()
    story.refresh_search_text()
    db.commit()
    db.refresh(story)
    return story


# ---------------------------------------------------------------------------
# DELETE /admin/stories/{story_id}  (org_admin only)
# ---------------------------------------------------------------------------

@router.delete("/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_story(
    story_id: str,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None)).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    story.deleted_at = now_ist()
    db.commit()


# ---------------------------------------------------------------------------
# POST /admin/stories/{story_id}/upload-image
# ---------------------------------------------------------------------------

@router.post("/stories/{story_id}/upload-image")
async def upload_story_image(
    story_id: str,
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    from ...services.storage import save_file

    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None)).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    media_url = save_file(contents, file.filename or "image.jpg", subfolder="story-images")

    # Append as a new paragraph with media_path
    paragraphs = list(story.paragraphs or [])
    paragraphs.append({
        "text": "",
        "type": "media",
        "media_path": media_url,
        "media_type": "photo",
        "media_name": file.filename or "image",
    })
    story.paragraphs = paragraphs
    story.updated_at = now_ist()
    story.refresh_search_text()
    db.commit()
    db.refresh(story)

    return {"media_url": media_url, "message": "Image uploaded"}
