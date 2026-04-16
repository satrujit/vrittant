import os
import uuid as uuid_mod
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File as FastAPIFile, status
from pydantic import BaseModel
from sqlalchemy import cast, func, or_, String
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.user import User, Entitlement
from ..models.story import Story
from ..models.story_revision import StoryRevision
from ..models.organization import Organization
from ..models.org_config import OrgConfig
from ..models.edition import Edition, EditionPage, EditionPageStory
from ..schemas.story import ParagraphSchema
from ..schemas.org_admin import (
    CreateUserRequest, UpdateUserRequest, UpdateUserRoleRequest,
    UpdateUserEntitlementsRequest, UserManagementResponse,
    UpdateOrgRequest, OrgResponse,
    UpdateOrgConfigRequest, OrgConfigResponse,
)
from ..deps import get_current_user, require_reviewer, get_current_org_id, require_org_admin
from ..utils.tz import now_ist, IST

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
    source: Optional[str] = None
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
    source: Optional[str] = None
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
    edition_info: Optional[EditionAssignmentInfo] = None

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

    model_config = {"from_attributes": True}


class AdminReporterListResponse(BaseModel):
    reporters: list[AdminReporterResponse]


# ---------------------------------------------------------------------------
# Helper: build a filtered story query (reused by multiple endpoints)
# ---------------------------------------------------------------------------

def _get_edition_info(db: Session, story_id: str) -> Optional[dict]:
    """Return edition assignment info for a story, or None."""
    row = (
        db.query(
            Edition.id.label("edition_id"),
            Edition.title.label("edition_title"),
            EditionPage.id.label("page_id"),
            EditionPage.page_name,
        )
        .join(EditionPage, EditionPage.edition_id == Edition.id)
        .join(EditionPageStory, EditionPageStory.edition_page_id == EditionPage.id)
        .filter(EditionPageStory.story_id == story_id)
        .first()
    )
    if not row:
        return None
    return {
        "edition_id": row.edition_id,
        "edition_title": row.edition_title,
        "page_id": row.page_id,
        "page_name": row.page_name,
    }


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


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsResponse)
def admin_stats(db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    pending_review = db.query(Story).filter(Story.organization_id == org_id, Story.status == "submitted").count()

    today_start = now_ist().replace(
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
# GET /admin/activity-heatmap
# Daily submission counts for all reporters (last 90 days)
# ---------------------------------------------------------------------------

class DayActivity(BaseModel):
    date: str  # YYYY-MM-DD
    count: int

class ReporterActivity(BaseModel):
    reporter_id: str
    reporter_name: str
    days: list[DayActivity]
    total: int

class TodayStatus(BaseModel):
    reporter_id: str
    reporter_name: str
    submitted: bool
    count: int

class ActivityHeatmapResponse(BaseModel):
    reporters: list[ReporterActivity]
    today_submitted: list[TodayStatus]
    avg_daily: float  # org average submissions per day


@router.get("/activity-heatmap", response_model=ActivityHeatmapResponse)
def activity_heatmap(
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    days: int = Query(90, ge=7, le=730),
    reporter_id: Optional[str] = Query(None),
):
    """Return per-reporter daily submission counts for the heatmap,
    plus today's submission status for each reporter.
    When reporter_id is provided, only return data for that single reporter."""
    from datetime import timedelta
    from sqlalchemy import cast, Date

    now = now_ist()
    start_date = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = now.strftime("%Y-%m-%d")

    # Submitted statuses (not drafts)
    submitted_statuses = ("submitted", "approved", "published", "rejected")

    if reporter_id:
        # Single-reporter mode: only fetch data for this reporter
        single_reporter = (
            db.query(User)
            .filter(User.id == reporter_id, User.organization_id == org_id)
            .first()
        )
        reporters = [single_reporter] if single_reporter else []
    else:
        # All active reporters in the org
        reporters = (
            db.query(User)
            .filter(User.organization_id == org_id, User.is_active == True)
            .all()
        )

    # Daily counts per reporter
    daily_q = (
        db.query(
            Story.reporter_id,
            cast(Story.submitted_at, Date).label("day"),
            func.count(Story.id).label("cnt"),
        )
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(submitted_statuses),
            Story.submitted_at >= start_date,
            Story.submitted_at.isnot(None),
        )
    )
    if reporter_id:
        daily_q = daily_q.filter(Story.reporter_id == reporter_id)
    daily_rows = daily_q.group_by(Story.reporter_id, cast(Story.submitted_at, Date)).all()

    # Build lookup: reporter_id -> {date_str: count}
    counts_map: dict[str, dict[str, int]] = {}
    for row in daily_rows:
        rid = row.reporter_id
        day_str = row.day.strftime("%Y-%m-%d") if hasattr(row.day, 'strftime') else str(row.day)
        counts_map.setdefault(rid, {})[day_str] = row.cnt

    # Total submissions in the period for org-wide average (always org-wide)
    if reporter_id:
        # For single-reporter mode, still compute org-wide avg for context
        org_total = (
            db.query(func.count(Story.id))
            .filter(
                Story.organization_id == org_id,
                Story.status.in_(submitted_statuses),
                Story.submitted_at >= start_date,
                Story.submitted_at.isnot(None),
            )
            .scalar()
        ) or 0
        total_submissions = org_total
    else:
        total_submissions = sum(r.cnt for r in daily_rows)
    active_days = max(days, 1)
    avg_daily = round(total_submissions / active_days, 2)

    # Build response
    reporter_activities = []
    today_statuses = []
    for r in reporters:
        r_counts = counts_map.get(r.id, {})
        day_list = [
            DayActivity(date=d, count=c)
            for d, c in sorted(r_counts.items())
        ]
        total = sum(c for c in r_counts.values())
        reporter_activities.append(
            ReporterActivity(
                reporter_id=r.id,
                reporter_name=r.name,
                days=day_list,
                total=total,
            )
        )
        if not reporter_id:
            today_count = r_counts.get(today_str, 0)
            today_statuses.append(
                TodayStatus(
                    reporter_id=r.id,
                    reporter_name=r.name,
                    submitted=today_count > 0,
                    count=today_count,
                )
            )

    # Sort: most active reporters first
    reporter_activities.sort(key=lambda x: x.total, reverse=True)
    if not reporter_id:
        # Sort today: submitted first, then by count desc
        today_statuses.sort(key=lambda x: (-int(x.submitted), -x.count, x.reporter_name))

    return ActivityHeatmapResponse(
        reporters=reporter_activities,
        today_submitted=today_statuses,
        avg_daily=avg_daily,
    )


# ---------------------------------------------------------------------------
# GET /admin/leaderboard
# ---------------------------------------------------------------------------

class BadgeInfo(BaseModel):
    key: str
    label: str

class LeaderboardEntry(BaseModel):
    reporter_id: str
    reporter_name: str
    rank: int
    points: float
    submissions: int
    approved: int
    current_streak: int
    badges: list[BadgeInfo]
    location: str = ""

class LeaderboardResponse(BaseModel):
    period: str
    entries: list[LeaderboardEntry]


BADGE_LABELS = {
    "first_story": "First Story",
    "on_fire": "On Fire",
    "unstoppable": "Unstoppable",
    "top_reporter": "Top Reporter",
    "century": "Century",
}

SUBMITTED_STATUSES = ("submitted", "approved", "published", "rejected")
APPROVED_STATUSES = ("approved", "published")


def _compute_current_streak(submission_dates: list, today) -> int:
    """Walk backwards from *today* counting consecutive days with a submission."""
    if not submission_dates:
        return 0
    date_set = {d for d in submission_dates}
    streak = 0
    day = today
    while day in date_set:
        streak += 1
        day -= timedelta(days=1)
    return streak


@router.get("/leaderboard", response_model=LeaderboardResponse)
def leaderboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    period: str = Query("month", regex="^(week|month|all)$"),
):
    from sqlalchemy import cast, Date

    now = now_ist()
    today = now.date()

    # ---- date range for base-point calculation ----
    if period == "week":
        period_start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        period_start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        period_start = None  # all time

    # ---- active reporters in org ----
    reporters = (
        db.query(User)
        .filter(User.organization_id == org_id, User.is_active == True, User.user_type == "reporter")
        .all()
    )
    reporter_map = {r.id: r for r in reporters}
    if not reporter_map:
        return LeaderboardResponse(period=period, entries=[])

    # ---- submission & approved counts (period-filtered) ----
    sub_q = (
        db.query(
            Story.reporter_id,
            func.count(Story.id).label("submissions"),
        )
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(SUBMITTED_STATUSES),
            Story.reporter_id.in_(list(reporter_map.keys())),
        )
    )
    if period_start is not None:
        sub_q = sub_q.filter(Story.submitted_at >= period_start)
    sub_rows = sub_q.group_by(Story.reporter_id).all()
    sub_map = {row.reporter_id: row.submissions for row in sub_rows}

    apr_q = (
        db.query(
            Story.reporter_id,
            func.count(Story.id).label("approved"),
        )
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(APPROVED_STATUSES),
            Story.reporter_id.in_(list(reporter_map.keys())),
        )
    )
    if period_start is not None:
        apr_q = apr_q.filter(Story.submitted_at >= period_start)
    apr_rows = apr_q.group_by(Story.reporter_id).all()
    apr_map = {row.reporter_id: row.approved for row in apr_rows}

    # ---- all-time approved count (for century badge) ----
    century_rows = (
        db.query(
            Story.reporter_id,
            func.count(Story.id).label("approved"),
        )
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(APPROVED_STATUSES),
            Story.reporter_id.in_(list(reporter_map.keys())),
        )
        .group_by(Story.reporter_id)
        .all()
    )
    alltime_approved = {row.reporter_id: row.approved for row in century_rows}

    # ---- streak: distinct submission dates per reporter (all time) ----
    streak_rows = (
        db.query(
            Story.reporter_id,
            cast(Story.submitted_at, Date).label("day"),
        )
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(SUBMITTED_STATUSES),
            Story.submitted_at.isnot(None),
            Story.reporter_id.in_(list(reporter_map.keys())),
        )
        .distinct()
        .all()
    )
    # group dates by reporter
    dates_by_reporter: dict[str, list] = {}
    for row in streak_rows:
        dates_by_reporter.setdefault(row.reporter_id, []).append(row.day)

    # ---- all-time submission existence (for first_story badge) ----
    any_sub_ids = {row.reporter_id for row in streak_rows}

    # ---- current-month top reporter (for top_reporter badge) ----
    month_start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    month_sub_q = (
        db.query(
            Story.reporter_id,
            func.count(Story.id).label("submissions"),
        )
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(SUBMITTED_STATUSES),
            Story.submitted_at >= month_start,
        )
        .group_by(Story.reporter_id)
        .all()
    )
    # find the reporter with most points in current month
    best_month_id = None
    best_month_pts = -1.0
    month_sub_map_tmp = {r.reporter_id: r.submissions for r in month_sub_q}
    month_apr_q = (
        db.query(
            Story.reporter_id,
            func.count(Story.id).label("approved"),
        )
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(APPROVED_STATUSES),
            Story.submitted_at >= month_start,
        )
        .group_by(Story.reporter_id)
        .all()
    )
    month_apr_map_tmp = {r.reporter_id: r.approved for r in month_apr_q}
    for rid in reporter_map:
        s = month_sub_map_tmp.get(rid, 0)
        a = month_apr_map_tmp.get(rid, 0)
        pts = s * 1.0 + a * 1.5
        streak = _compute_current_streak(dates_by_reporter.get(rid, []), today)
        pts += (streak // 7) * 5 + (streak // 30) * 20
        if pts > best_month_pts:
            best_month_pts = pts
            best_month_id = rid

    # ---- build entries ----
    entries: list[LeaderboardEntry] = []
    for rid, reporter in reporter_map.items():
        submissions = sub_map.get(rid, 0)
        approved = apr_map.get(rid, 0)
        streak = _compute_current_streak(dates_by_reporter.get(rid, []), today)

        streak_bonus = (streak // 7) * 5 + (streak // 30) * 20
        points = submissions * 1.0 + approved * 1.5 + streak_bonus

        # badges
        badges: list[BadgeInfo] = []
        if rid in any_sub_ids:
            badges.append(BadgeInfo(key="first_story", label=BADGE_LABELS["first_story"]))
        if streak >= 7:
            badges.append(BadgeInfo(key="on_fire", label=BADGE_LABELS["on_fire"]))
        if streak >= 30:
            badges.append(BadgeInfo(key="unstoppable", label=BADGE_LABELS["unstoppable"]))
        if rid == best_month_id and best_month_pts > 0:
            badges.append(BadgeInfo(key="top_reporter", label=BADGE_LABELS["top_reporter"]))
        if alltime_approved.get(rid, 0) >= 100:
            badges.append(BadgeInfo(key="century", label=BADGE_LABELS["century"]))

        entries.append(LeaderboardEntry(
            reporter_id=rid,
            reporter_name=reporter.name,
            rank=0,  # assigned after sorting
            points=round(points, 1),
            submissions=submissions,
            approved=approved,
            current_streak=streak,
            badges=badges,
            location=reporter.area_name or "",
        ))

    # sort by points desc, then by name for deterministic tie-breaking
    entries.sort(key=lambda e: (-e.points, e.reporter_name))
    for i, entry in enumerate(entries, start=1):
        entry.rank = i

    return LeaderboardResponse(period=period, entries=entries)


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
# GET /admin/stories/semantic-search  (cross-language semantic search)
# ---------------------------------------------------------------------------

@router.get("/stories/semantic-search", response_model=AdminStoryListResponse)
async def semantic_search_stories(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Cross-language fuzzy search using pg_trgm trigram similarity.
    Translates query via Sarvam AI so English queries find Odia stories and vice versa.
    Typo-tolerant: "Yojaya" still matches "Yojana".
    """
    import re
    import httpx
    from sqlalchemy import func, desc, literal_column
    from ..config import settings

    import logging as _logging
    _log = _logging.getLogger(__name__)

    # --- Step 1: Translate query for cross-language support ---
    has_odia = bool(re.search(r'[\u0B00-\u0B7F]', q))
    source_lang = "od-IN" if has_odia else "en-IN"
    target_lang = "en-IN" if has_odia else "od-IN"

    translated_text = ""
    try:
        translate_url = f"{settings.SARVAM_BASE_URL}/translate"
        headers = {
            "api-subscription-key": settings.SARVAM_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "input": q,
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "model": "mayura:v1",
        }
        _log.info("Search: translating query=%r (%s -> %s)", q, source_lang, target_lang)
        async with httpx.AsyncClient() as client:
            resp = await client.post(translate_url, json=payload, headers=headers, timeout=15.0)
            resp.raise_for_status()
            translated_text = resp.json().get("translated_text", "")
        _log.info("Search: translated %r -> %r", q, translated_text)
    except Exception as exc:
        _log.warning("Sarvam translate failed (continuing with original query): %s", exc)

    # --- Step 2: Build search terms (original + translated + individual words) ---
    all_terms = [q]
    if translated_text and translated_text.strip() and translated_text != q:
        all_terms.append(translated_text.strip())

    # Also add individual words (>=3 chars) for partial matching
    for term in list(all_terms):
        words = term.split()
        for w in words:
            if len(w) >= 3 and w not in all_terms:
                all_terms.append(w)

    _log.info("Search: terms=%s", all_terms)

    # --- Step 3: Trigram similarity search on search_text column ---
    # Use word_similarity for better substring matching within long text
    # Also fall back to ILIKE for exact substring matches (trigrams can miss short words)
    conditions = []
    similarity_exprs = []

    for term in all_terms:
        # Trigram word similarity (finds best matching substring)
        sim_expr = func.word_similarity(term, Story.search_text)
        similarity_exprs.append(sim_expr)
        conditions.append(sim_expr > 0.25)
        # Also plain ILIKE as fallback for exact substring matches
        conditions.append(Story.search_text.ilike(f"%{term}%"))

    # Best similarity score across all terms for ranking
    best_similarity = func.greatest(*similarity_exprs) if len(similarity_exprs) > 1 else similarity_exprs[0]

    base_query = (
        db.query(Story, best_similarity.label("score"))
        .options(joinedload(Story.reporter), joinedload(Story.revision))
        .filter(
            Story.organization_id == org_id,
            Story.status != "draft",
            or_(*conditions),
        )
    )

    total = base_query.count()
    results = (
        base_query
        .order_by(desc("score"), Story.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    _log.info("Search: found %d results for query=%r", total, q)

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
        for s, score in results
    ]

    return AdminStoryListResponse(stories=items, total=total)


# ---------------------------------------------------------------------------
# GET /admin/stories/{story_id}/related  (trigram similarity on headline)
# ---------------------------------------------------------------------------

class RelatedStoryItem(BaseModel):
    id: str
    headline: str
    status: str | None = None
    location: str | None = None
    created_at: datetime | None = None
    image_url: str | None = None
    reporter_name: str | None = None

    model_config = {"from_attributes": True}


@router.get("/stories/{story_id}/related", response_model=list[RelatedStoryItem])
def get_related_stories(
    story_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    """Find stories related to a given story using pg_trgm trigram similarity on headline."""
    from sqlalchemy import text

    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    if not story.headline:
        return []

    rows = db.execute(
        text("""
            SELECT s.id, s.headline, s.status, s.location, s.created_at,
                   s.paragraphs, u.name AS reporter_name,
                   similarity(s.search_text, :headline) AS sim
            FROM stories s
            LEFT JOIN users u ON s.reporter_id = u.id
            WHERE s.id != :story_id
              AND s.organization_id = :org_id
              AND similarity(s.search_text, :headline) > 0.15
            ORDER BY sim DESC
            LIMIT 10
        """),
        {"headline": story.headline, "story_id": story_id, "org_id": org_id},
    ).fetchall()

    results = []
    for r in rows:
        # Extract first image URL from paragraphs (media paragraphs have type="media")
        image_url = None
        paragraphs = r.paragraphs
        if paragraphs and isinstance(paragraphs, list):
            for p in paragraphs:
                if isinstance(p, dict) and p.get("type") == "media" and p.get("media_path"):
                    image_url = p["media_path"]
                    break

        results.append(RelatedStoryItem(
            id=r.id,
            headline=r.headline,
            status=r.status,
            location=r.location,
            created_at=r.created_at,
            image_url=image_url,
            reporter_name=r.reporter_name,
        ))

    return results


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
        .filter(Story.id == story_id, Story.organization_id == org_id)
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
        .filter(Story.id == story_id, Story.organization_id == org_id)
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
# GET /admin/reporters
# ---------------------------------------------------------------------------

@router.get("/reporters", response_model=AdminReporterListResponse)
def admin_list_reporters(
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    include_inactive: bool = Query(False, description="Include deactivated/deleted users"),
):
    query = db.query(User).filter(User.organization_id == org_id)
    if not include_inactive:
        query = query.filter(User.is_active == True)
    all_users = query.all()

    # Resolve org name once (all users share the same org)
    from ..models.organization import Organization
    org = db.query(Organization).filter(Organization.id == org_id).first()
    org_name = org.name if org else ""

    # Statuses that count as "submitted" (excludes drafts)
    submitted_statuses = ("submitted", "approved", "published", "rejected")

    result = []
    for r in all_users:
        submission_count = (
            db.query(func.count(Story.id))
            .filter(Story.reporter_id == r.id, Story.status.in_(submitted_statuses))
            .scalar()
        )
        published_count = (
            db.query(func.count(Story.id))
            .filter(Story.reporter_id == r.id, Story.status == "published")
            .scalar()
        )
        last_story = (
            db.query(Story.submitted_at)
            .filter(Story.reporter_id == r.id, Story.submitted_at.isnot(None))
            .order_by(Story.submitted_at.desc())
            .first()
        )
        last_active = last_story[0] if last_story else None

        result.append(
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
                submission_count=submission_count,
                published_count=published_count,
                last_active=last_active,
                entitlements=[e.page_key for e in r.entitlements],
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
@router.put("/org/logo", response_model=OrgResponse)
async def update_org_logo(
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    from ..services.storage import save_logo
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed for logos")
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo file too large (max 5 MB)")
    org.logo_url = save_logo(contents, org.slug, ext)
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
        from ..models.org_config import (
            DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
            DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
        )
        config = OrgConfig(
            organization_id=org_id,
            categories=DEFAULT_CATEGORIES,
            publication_types=DEFAULT_PUBLICATION_TYPES,
            page_suggestions=DEFAULT_PAGE_SUGGESTIONS,
            priority_levels=DEFAULT_PRIORITY_LEVELS,
            default_language="odia",
        )
        db.add(config)
        db.commit()
        db.refresh(config)
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
        config = OrgConfig(organization_id=org_id)
        db.add(config)
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
        from ..models.org_config import (
            DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
            DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
        )
        config = OrgConfig(
            organization_id=org_id,
            categories=DEFAULT_CATEGORIES,
            publication_types=DEFAULT_PUBLICATION_TYPES,
            page_suggestions=DEFAULT_PAGE_SUGGESTIONS,
            priority_levels=DEFAULT_PRIORITY_LEVELS,
            default_language="odia",
        )
        db.add(config)
        db.commit()
        db.refresh(config)
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
    from ..services.storage import save_file

    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id).first()
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
