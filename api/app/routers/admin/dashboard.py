"""Admin dashboard endpoints: stats and per-reporter activity heatmap."""
from datetime import timedelta
from typing import Optional

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import get_current_org_id, require_reviewer
from ...models.story import Story
from ...models.user import User
from ...utils.tz import now_ist
from . import router
from ._shared import StatsResponse


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=StatsResponse)
def admin_stats(db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    pending_review = db.query(Story).filter(Story.organization_id == org_id, Story.status == "submitted", Story.deleted_at.is_(None)).count()

    today_start = now_ist().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    reviewed_today = (
        db.query(Story)
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(["approved", "rejected", "published"]),
            Story.updated_at >= today_start,
            Story.deleted_at.is_(None),
        )
        .count()
    )

    total_published = db.query(Story).filter(Story.organization_id == org_id, Story.status == "published", Story.deleted_at.is_(None)).count()
    total_stories = db.query(Story).filter(Story.organization_id == org_id, Story.status != "draft", Story.deleted_at.is_(None)).count()
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
            Story.deleted_at.is_(None),
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
                Story.deleted_at.is_(None),
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
