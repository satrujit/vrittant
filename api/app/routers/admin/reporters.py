"""Admin reporter endpoints: list reporters, list a reporter's stories."""
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ...database import get_db
from ...deps import get_current_org_id, require_reviewer
from ...models.organization import Organization
from ...models.story import Story
from ...models.user import User
from ...utils.scope import get_owned_or_404
from . import router
from ._shared import (
    AdminReporterListResponse,
    AdminReporterResponse,
    AdminStoryListItem,
    AdminStoryListResponse,
    _build_story_query,
)


# ---------------------------------------------------------------------------
# GET /admin/reporters
# ---------------------------------------------------------------------------

@router.get("/reporters", response_model=AdminReporterListResponse)
def admin_list_reporters(
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    include_inactive: bool = Query(False, description="Include deactivated/deleted users"),
    updated_since: Optional[str] = Query(None, description="ISO timestamp — return only reporters updated after this time"),
):
    query = db.query(User).options(joinedload(User.entitlements)).filter(User.organization_id == org_id)

    if updated_since:
        # Delta mode: include soft-deleted users changed since the timestamp
        try:
            dt = datetime.fromisoformat(updated_since)
        except (ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid updated_since timestamp")
        query = query.filter(or_(User.updated_at >= dt, User.deleted_at >= dt))
    else:
        # Normal mode: respect include_inactive flag
        if not include_inactive:
            query = query.filter(User.is_active == True)

    all_users = query.all()
    user_ids = [u.id for u in all_users]

    if not user_ids:
        return AdminReporterListResponse(reporters=[])

    # Resolve org name once
    org = db.query(Organization).filter(Organization.id == org_id).first()
    org_name = org.name if org else ""

    # Batch: submission counts per reporter (single query)
    submitted_statuses = ("submitted", "approved", "published", "rejected")
    sub_rows = (
        db.query(Story.reporter_id, func.count(Story.id).label("cnt"))
        .filter(Story.reporter_id.in_(user_ids), Story.status.in_(submitted_statuses), Story.deleted_at.is_(None))
        .group_by(Story.reporter_id)
        .all()
    )
    sub_map = {row.reporter_id: row.cnt for row in sub_rows}

    # Batch: published counts per reporter (single query)
    pub_rows = (
        db.query(Story.reporter_id, func.count(Story.id).label("cnt"))
        .filter(Story.reporter_id.in_(user_ids), Story.status == "published", Story.deleted_at.is_(None))
        .group_by(Story.reporter_id)
        .all()
    )
    pub_map = {row.reporter_id: row.cnt for row in pub_rows}

    # Batch: last active per reporter (single query)
    last_rows = (
        db.query(Story.reporter_id, func.max(Story.submitted_at).label("last"))
        .filter(Story.reporter_id.in_(user_ids), Story.submitted_at.isnot(None), Story.deleted_at.is_(None))
        .group_by(Story.reporter_id)
        .all()
    )
    last_map = {row.reporter_id: row.last for row in last_rows}

    result = [
        AdminReporterResponse(
            id=r.id,
            name=r.name,
            phone=r.phone,
            area_name=r.area_name,
            organization=org_name,
            user_type=r.user_type,
            is_active=r.is_active,
            created_at=r.created_at,
            updated_at=r.updated_at,
            submission_count=sub_map.get(r.id, 0),
            published_count=pub_map.get(r.id, 0),
            last_active=last_map.get(r.id),
            entitlements=[e.page_key for e in r.entitlements],
            is_deleted=r.deleted_at is not None,
        )
        for r in all_users
    ]

    return AdminReporterListResponse(reporters=result)


# ---------------------------------------------------------------------------
# GET /admin/reporters/{reporter_id}/stories
# ---------------------------------------------------------------------------

@router.get(
    "/reporters/{reporter_id}/stories", response_model=AdminStoryListResponse
)
def admin_reporter_stories(
    reporter_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    recent: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    # Verify reporter exists and belongs to the same organization
    get_owned_or_404(db, User, reporter_id, org_id)

    query = _build_story_query(
        db,
        org_id=org_id,
        reporter_id=reporter_id,
        status_filter=status_filter,
        category=category,
        search=search,
        date_from=date_from,
        date_to=date_to,
        recent=recent,
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
