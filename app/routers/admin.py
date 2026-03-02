import os
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File as FastAPIFile, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.user import User, Entitlement
from ..models.story import Story
from ..models.story_revision import StoryRevision
from ..models.organization import Organization
from ..models.org_config import OrgConfig
from ..schemas.story import ParagraphSchema
from ..schemas.org_admin import (
    CreateUserRequest, UpdateUserRequest, UpdateUserRoleRequest,
    UpdateUserEntitlementsRequest, UserManagementResponse,
    UpdateOrgRequest, OrgResponse,
    UpdateOrgConfigRequest, OrgConfigResponse,
)
from ..deps import get_current_user, require_reviewer, get_current_org_id, require_org_admin

router = APIRouter(prefix="/admin", tags=["admin"])
config_router = APIRouter(prefix="/config", tags=["config"])

# ---------------------------------------------------------------------------
# Pydantic schemas specific to admin endpoints
# ---------------------------------------------------------------------------

class AdminReporterInfo(BaseModel):
    id: str
    name: str
    phone: str
    area_name: str
    organization: str

    model_config = {"from_attributes": True}


class AdminStoryResponse(BaseModel):
    id: str
    reporter_id: str
    headline: str
    category: Optional[str]
    location: Optional[str]
    priority: Optional[str] = "normal"
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reporter: AdminReporterInfo

    model_config = {"from_attributes": True}


class AdminStoryListItem(BaseModel):
    id: str
    reporter_id: str
    headline: str
    category: Optional[str]
    location: Optional[str]
    priority: Optional[str] = "normal"
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reporter: AdminReporterInfo
    has_revision: bool = False

    model_config = {"from_attributes": True}


class AdminStoryListResponse(BaseModel):
    stories: list[AdminStoryListItem]
    total: int


class AdminRevisionInfo(BaseModel):
    id: str
    editor_id: str
    headline: str
    paragraphs: list[dict]
    layout_config: Optional[dict] = None
    english_translation: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminStoryWithRevisionResponse(BaseModel):
    id: str
    reporter_id: str
    headline: str
    category: Optional[str]
    location: Optional[str]
    priority: Optional[str] = "normal"
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reporter: AdminReporterInfo
    revision: Optional[AdminRevisionInfo] = None

    model_config = {"from_attributes": True}


class StatsResponse(BaseModel):
    pending_review: int
    reviewed_today: int
    avg_ai_accuracy: float
    total_published: int
    total_stories: int
    total_reporters: int


class StatusUpdate(BaseModel):
    status: str  # approved | rejected | published | in_progress
    reason: Optional[str] = None


class AdminStoryUpdate(BaseModel):
    headline: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    paragraphs: Optional[list[ParagraphSchema]] = None
    layout_config: Optional[dict] = None
    english_translation: Optional[str] = None


class AdminReporterResponse(BaseModel):
    id: str
    name: str
    phone: str
    area_name: str
    organization: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    submission_count: int
    published_count: int
    last_active: Optional[datetime]

    model_config = {"from_attributes": True}


class AdminReporterListResponse(BaseModel):
    reporters: list[AdminReporterResponse]


# ---------------------------------------------------------------------------
# Helper: build a filtered story query (reused by multiple endpoints)
# ---------------------------------------------------------------------------

def _build_story_query(
    db: Session,
    *,
    org_id: str,
    reporter_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    exclude_status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    location: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    recent: bool = False,
    exclude_drafts: bool = True,
):
    query = db.query(Story).options(joinedload(Story.reporter)).filter(Story.organization_id == org_id)

    if reporter_id:
        query = query.filter(Story.reporter_id == reporter_id)
    if status_filter:
        query = query.filter(Story.status == status_filter)
    if exclude_status:
        query = query.filter(Story.status != exclude_status)
    # Auto-exclude drafts from admin views unless explicitly requesting them
    if exclude_drafts and not status_filter and not exclude_status:
        query = query.filter(Story.status != "draft")
    if category:
        query = query.filter(Story.category == category)
    if search:
        query = query.filter(Story.headline.ilike(f"%{search}%"))
    if location:
        query = query.filter(Story.location.ilike(f"%{location}%"))
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(Story.created_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
            query = query.filter(Story.created_at <= dt)
        except ValueError:
            pass
    if recent:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        query = query.filter(Story.created_at >= cutoff)

    return query


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsResponse)
def admin_stats(db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    pending_review = db.query(Story).filter(Story.organization_id == org_id, Story.status == "submitted").count()

    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    reviewed_today = (
        db.query(Story)
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(["approved", "rejected", "published"]),
            Story.updated_at >= today_start,
        )
        .count()
    )

    total_published = db.query(Story).filter(Story.organization_id == org_id, Story.status == "published").count()
    total_stories = db.query(Story).filter(Story.organization_id == org_id, Story.status != "draft").count()
    total_reporters = db.query(User).filter(User.user_type == "reporter", User.organization_id == org_id).count()

    return StatsResponse(
        pending_review=pending_review,
        reviewed_today=reviewed_today,
        avg_ai_accuracy=94.2,
        total_published=total_published,
        total_stories=total_stories,
        total_reporters=total_reporters,
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
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
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
# GET /admin/stories/{story_id}
# ---------------------------------------------------------------------------

@router.get("/stories/{story_id}", response_model=AdminStoryWithRevisionResponse)
def admin_get_story(story_id: str, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    story = (
        db.query(Story)
        .options(joinedload(Story.reporter), joinedload(Story.revision))
        .filter(Story.id == story_id, Story.organization_id == org_id)
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )
    return story


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
        .filter(Story.id == story_id, Story.organization_id == org_id)
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )

    story.status = body.status
    story.updated_at = datetime.now(timezone.utc)
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
        .filter(Story.id == story_id, Story.organization_id == org_id)
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )

    # Build revision data from request body
    rev_headline = body.headline if body.headline is not None else story.headline
    rev_paragraphs = (
        [p.model_dump() for p in body.paragraphs]
        if body.paragraphs is not None
        else story.paragraphs
    )

    # Upsert: update existing revision or create new one
    existing_rev = story.revision
    if existing_rev:
        existing_rev.headline = rev_headline
        existing_rev.paragraphs = rev_paragraphs
        if body.layout_config is not None:
            existing_rev.layout_config = body.layout_config
        if body.english_translation is not None:
            existing_rev.english_translation = body.english_translation
        existing_rev.updated_at = datetime.now(timezone.utc)
    else:
        new_rev = StoryRevision(
            story_id=story.id,
            editor_id=current_user.id,
            headline=rev_headline,
            paragraphs=rev_paragraphs,
            layout_config=body.layout_config,
            english_translation=body.english_translation,
        )
        db.add(new_rev)

    # Update category on the story if provided (category is story-level, not content)
    if body.category is not None:
        story.category = body.category
    if body.priority is not None:
        story.priority = body.priority

    story.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(story)
    return story


# ---------------------------------------------------------------------------
# GET /admin/reporters
# ---------------------------------------------------------------------------

@router.get("/reporters", response_model=AdminReporterListResponse)
def admin_list_reporters(db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    reporters = db.query(User).filter(User.user_type == "reporter", User.organization_id == org_id).all()

    result = []
    for r in reporters:
        submission_count = (
            db.query(func.count(Story.id))
            .filter(Story.reporter_id == r.id)
            .scalar()
        )
        published_count = (
            db.query(func.count(Story.id))
            .filter(Story.reporter_id == r.id, Story.status == "published")
            .scalar()
        )
        last_story = (
            db.query(Story.updated_at)
            .filter(Story.reporter_id == r.id)
            .order_by(Story.updated_at.desc())
            .first()
        )
        last_active = last_story[0] if last_story else None

        result.append(
            AdminReporterResponse(
                id=r.id,
                name=r.name,
                phone=r.phone,
                area_name=r.area_name,
                organization=r.organization,
                is_active=r.is_active,
                created_at=r.created_at,
                updated_at=r.updated_at,
                submission_count=submission_count,
                published_count=published_count,
                last_active=last_active,
            )
        )

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
    reporter = db.query(User).filter(User.id == reporter_id, User.organization_id == org_id).first()
    if not reporter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reporter not found"
        )

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


# ===========================================================================
# Org-admin endpoints (Tasks 4-7)
# ===========================================================================

# ---------------------------------------------------------------------------
# POST /admin/users  (org_admin only)
# ---------------------------------------------------------------------------
@router.post("/users", response_model=UserManagementResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    existing = db.query(User).filter(User.phone == body.phone).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    user = User(
        name=body.name, phone=body.phone, email=body.email, area_name=body.area_name,
        user_type=body.user_type, organization=org.name if org else "", organization_id=org_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserManagementResponse(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        user_type=user.user_type, area_name=user.area_name, is_active=user.is_active,
        entitlements=[e.page_key for e in user.entitlements],
    )


# ---------------------------------------------------------------------------
# PUT /admin/users/{user_id}  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/users/{user_id}", response_model=UserManagementResponse)
def update_user(
    user_id: str, body: UpdateUserRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if body.name is not None: user.name = body.name
    if body.email is not None: user.email = body.email
    if body.area_name is not None: user.area_name = body.area_name
    if body.is_active is not None: user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return UserManagementResponse(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        user_type=user.user_type, area_name=user.area_name, is_active=user.is_active,
        entitlements=[e.page_key for e in user.entitlements],
    )


# ---------------------------------------------------------------------------
# PUT /admin/users/{user_id}/role  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/users/{user_id}/role", response_model=UserManagementResponse)
def update_user_role(
    user_id: str, body: UpdateUserRoleRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.user_type = body.user_type
    db.commit()
    db.refresh(user)
    return UserManagementResponse(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        user_type=user.user_type, area_name=user.area_name, is_active=user.is_active,
        entitlements=[e.page_key for e in user.entitlements],
    )


# ---------------------------------------------------------------------------
# PUT /admin/users/{user_id}/entitlements  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/users/{user_id}/entitlements", response_model=UserManagementResponse)
def update_user_entitlements(
    user_id: str, body: UpdateUserEntitlementsRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db.query(Entitlement).filter(Entitlement.user_id == user_id).delete()
    for key in body.page_keys:
        db.add(Entitlement(user_id=user_id, page_key=key))
    db.commit()
    db.refresh(user)
    return UserManagementResponse(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        user_type=user.user_type, area_name=user.area_name, is_active=user.is_active,
        entitlements=[e.page_key for e in user.entitlements],
    )


# ---------------------------------------------------------------------------
# PUT /admin/org  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/org", response_model=OrgResponse)
def update_org(
    body: UpdateOrgRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if body.name is not None: org.name = body.name
    if body.theme_color is not None: org.theme_color = body.theme_color
    db.commit()
    db.refresh(org)
    return org


# ---------------------------------------------------------------------------
# PUT /admin/org/logo  (org_admin only)
# ---------------------------------------------------------------------------
LOGO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "org-logos")
os.makedirs(LOGO_DIR, exist_ok=True)


@router.put("/org/logo", response_model=OrgResponse)
async def update_org_logo(
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed for logos")
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo file too large (max 5 MB)")
    filename = f"{org.slug}{ext}"
    filepath = os.path.join(LOGO_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)
    org.logo_url = f"/uploads/org-logos/{filename}"
    db.commit()
    db.refresh(org)
    return org


# ---------------------------------------------------------------------------
# GET /admin/config  (org_admin only)
# ---------------------------------------------------------------------------
@router.get("/config", response_model=OrgConfigResponse)
def get_org_config(
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    config = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return config


# ---------------------------------------------------------------------------
# PUT /admin/config  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/config", response_model=OrgConfigResponse)
def update_org_config(
    body: UpdateOrgConfigRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    config = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    if body.categories is not None:
        config.categories = [c.model_dump() for c in body.categories]
    if body.publication_types is not None:
        config.publication_types = [p.model_dump() for p in body.publication_types]
    if body.page_suggestions is not None:
        config.page_suggestions = [p.model_dump() for p in body.page_suggestions]
    if body.priority_levels is not None:
        config.priority_levels = [p.model_dump() for p in body.priority_levels]
    if body.default_language is not None:
        config.default_language = body.default_language
    db.commit()
    db.refresh(config)
    return config


# ---------------------------------------------------------------------------
# GET /config/me  (any authenticated user)
# ---------------------------------------------------------------------------
@config_router.get("/me", response_model=OrgConfigResponse)
def get_my_org_config(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
):
    config = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return config


# ---------------------------------------------------------------------------
# DELETE /admin/stories/{story_id}  (org_admin only)
# ---------------------------------------------------------------------------
@router.delete("/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_story(
    story_id: str,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    if story.revision:
        db.delete(story.revision)
    db.delete(story)
    db.commit()
