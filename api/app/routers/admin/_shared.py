"""Schemas and query helpers shared across admin sub-modules."""
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import cast, or_, String
from sqlalchemy.orm import Session, joinedload

from ...models.story import Story
from ...models.edition import Edition, EditionPage, EditionPageStory
from ...schemas.story import ParagraphSchema
from ...utils.tz import now_ist, IST


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
    source: Optional[str] = None
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reporter: AdminReporterInfo
    reviewed_by: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdminStoryListItem(BaseModel):
    id: str
    reporter_id: str
    headline: str
    category: Optional[str]
    location: Optional[str]
    priority: Optional[str] = "normal"
    source: Optional[str] = None
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reporter: AdminReporterInfo
    has_revision: bool = False
    is_deleted: bool = False
    reviewed_by: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None

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
    social_posts: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EditionAssignmentInfo(BaseModel):
    edition_id: str
    edition_title: str
    page_id: str
    page_name: str


class AdminStoryWithRevisionResponse(BaseModel):
    id: str
    reporter_id: str
    headline: str
    category: Optional[str]
    location: Optional[str]
    priority: Optional[str] = "normal"
    source: Optional[str] = None
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reporter: AdminReporterInfo
    revision: Optional[AdminRevisionInfo] = None
    edition_info: list[EditionAssignmentInfo] = []
    reviewed_by: Optional[str] = None
    reviewer_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None

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
    social_posts: Optional[dict] = None


class AdminReporterResponse(BaseModel):
    id: str
    name: str
    phone: str
    area_name: str
    organization: str
    user_type: str = "reporter"
    is_active: bool
    created_at: datetime
    updated_at: datetime
    submission_count: int
    published_count: int
    last_active: Optional[datetime]
    entitlements: list[str] = []
    is_deleted: bool = False

    model_config = {"from_attributes": True}


class AdminReporterListResponse(BaseModel):
    reporters: list[AdminReporterResponse]


# ---------------------------------------------------------------------------
# Helper: build a filtered story query (reused by multiple endpoints)
# ---------------------------------------------------------------------------

def _get_edition_info(db: Session, story_id: str) -> list[dict]:
    """Return all edition assignments for a story."""
    rows = (
        db.query(
            Edition.id.label("edition_id"),
            Edition.title.label("edition_title"),
            EditionPage.id.label("page_id"),
            EditionPage.page_name,
        )
        .join(EditionPage, EditionPage.edition_id == Edition.id)
        .join(EditionPageStory, EditionPageStory.edition_page_id == EditionPage.id)
        .filter(EditionPageStory.story_id == story_id)
        .all()
    )
    return [
        {
            "edition_id": r.edition_id,
            "edition_title": r.edition_title,
            "page_id": r.page_id,
            "page_name": r.page_name,
        }
        for r in rows
    ]


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
    available_for_edition: Optional[str] = None,
):
    query = db.query(Story).options(joinedload(Story.reporter)).filter(Story.organization_id == org_id, Story.deleted_at.is_(None))

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
        like_pat = f"%{search}%"
        query = query.filter(
            or_(
                Story.headline.ilike(like_pat),
                Story.location.ilike(like_pat),
                cast(Story.paragraphs, String).ilike(like_pat),
            )
        )
    if location:
        query = query.filter(Story.location.ilike(f"%{location}%"))
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=IST)
            query = query.filter(Story.created_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=IST
            )
            query = query.filter(Story.created_at <= dt)
        except ValueError:
            pass
    if recent:
        cutoff = now_ist() - timedelta(hours=24)
        query = query.filter(Story.created_at >= cutoff)

    # Exclude stories already assigned to OTHER editions (keep those in the given edition)
    if available_for_edition:
        other_edition_story_ids = (
            db.query(EditionPageStory.story_id)
            .join(EditionPage, EditionPage.id == EditionPageStory.edition_page_id)
            .filter(EditionPage.edition_id != available_for_edition)
            .subquery()
        )
        query = query.filter(~Story.id.in_(other_edition_story_ids))

    return query
