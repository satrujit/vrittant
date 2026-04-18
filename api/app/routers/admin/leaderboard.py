"""Admin leaderboard endpoint: per-reporter points, streaks, badges."""
from datetime import timedelta

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import get_current_org_id, require_reviewer
from ...models.story import Story
from ...models.user import User
from ...utils.tz import now_ist
from . import router


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

    month_start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)

    # ---- active reporters in org ----
    reporters = (
        db.query(User)
        .filter(User.organization_id == org_id, User.is_active == True, User.user_type == "reporter")
        .all()
    )
    reporter_map = {r.id: r for r in reporters}
    if not reporter_map:
        return LeaderboardResponse(period=period, entries=[])

    reporter_ids = list(reporter_map.keys())

    # ---- Q1: period-filtered submissions + approved (conditional aggregation) ----
    period_q = (
        db.query(
            Story.reporter_id,
            func.count(Story.id).label("submissions"),
            func.count(case((Story.status.in_(APPROVED_STATUSES), Story.id))).label("approved"),
        )
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(SUBMITTED_STATUSES),
            Story.reporter_id.in_(reporter_ids),
            Story.deleted_at.is_(None),
        )
    )
    # Period bucketing uses created_at, not submitted_at. submitted_at can
    # be rewritten when a story is re-saved/approved/republished, which
    # caused stories to "leave" the month window even though they were
    # clearly created within it (and showed up in the week tally).
    if period_start is not None:
        period_q = period_q.filter(Story.created_at >= period_start)
    period_rows = period_q.group_by(Story.reporter_id).all()
    sub_map = {row.reporter_id: row.submissions for row in period_rows}
    apr_map = {row.reporter_id: row.approved for row in period_rows}

    # ---- Q2: all-time approved count (century badge) + monthly counts (top reporter) ----
    # When period == "all", the period query already gives all-time counts,
    # so we only need monthly data for top_reporter.
    # When period == "month", period query already gives monthly counts,
    # so we only need all-time approved for century badge.
    # When period == "week", we need both all-time approved AND monthly counts.
    if period == "all":
        # Period query already has all-time approved; just need monthly for top_reporter
        alltime_approved = dict(apr_map)
        month_rows = (
            db.query(
                Story.reporter_id,
                func.count(Story.id).label("submissions"),
                func.count(case((Story.status.in_(APPROVED_STATUSES), Story.id))).label("approved"),
            )
            .filter(
                Story.organization_id == org_id,
                Story.status.in_(SUBMITTED_STATUSES),
                Story.created_at >= month_start,
                Story.deleted_at.is_(None),
            )
            .group_by(Story.reporter_id)
            .all()
        )
        month_sub_map = {r.reporter_id: r.submissions for r in month_rows}
        month_apr_map = {r.reporter_id: r.approved for r in month_rows}
    elif period == "month":
        # Period query already has monthly counts; just need all-time approved for century
        month_sub_map = dict(sub_map)
        month_apr_map = dict(apr_map)
        century_rows = (
            db.query(
                Story.reporter_id,
                func.count(Story.id).label("approved"),
            )
            .filter(
                Story.organization_id == org_id,
                Story.status.in_(APPROVED_STATUSES),
                Story.reporter_id.in_(reporter_ids),
                Story.deleted_at.is_(None),
            )
            .group_by(Story.reporter_id)
            .all()
        )
        alltime_approved = {row.reporter_id: row.approved for row in century_rows}
    else:
        # period == "week": need all-time approved AND monthly counts in one query
        alltime_and_month_rows = (
            db.query(
                Story.reporter_id,
                func.count(case((Story.status.in_(APPROVED_STATUSES), Story.id))).label("alltime_approved"),
                func.count(case((Story.created_at >= month_start, Story.id))).label("month_submissions"),
                func.count(case(
                    (Story.status.in_(APPROVED_STATUSES) & (Story.created_at >= month_start), Story.id),
                )).label("month_approved"),
            )
            .filter(
                Story.organization_id == org_id,
                Story.status.in_(SUBMITTED_STATUSES),
                Story.reporter_id.in_(reporter_ids),
                Story.deleted_at.is_(None),
            )
            .group_by(Story.reporter_id)
            .all()
        )
        alltime_approved = {r.reporter_id: r.alltime_approved for r in alltime_and_month_rows}
        month_sub_map = {r.reporter_id: r.month_submissions for r in alltime_and_month_rows}
        month_apr_map = {r.reporter_id: r.month_approved for r in alltime_and_month_rows}

    # ---- Q3: streak — distinct submission dates per reporter (all time) ----
    streak_rows = (
        db.query(
            Story.reporter_id,
            cast(Story.submitted_at, Date).label("day"),
        )
        .filter(
            Story.organization_id == org_id,
            Story.status.in_(SUBMITTED_STATUSES),
            Story.submitted_at.isnot(None),
            Story.reporter_id.in_(reporter_ids),
            Story.deleted_at.is_(None),
        )
        .distinct()
        .all()
    )
    # group dates by reporter
    dates_by_reporter: dict[str, list] = {}
    for row in streak_rows:
        dates_by_reporter.setdefault(row.reporter_id, []).append(row.day)

    # first_story badge: any reporter who has at least one submission
    any_sub_ids = {row.reporter_id for row in streak_rows}

    # ---- determine top reporter for current month ----
    best_month_id = None
    best_month_pts = -1.0
    for rid in reporter_map:
        s = month_sub_map.get(rid, 0)
        a = month_apr_map.get(rid, 0)
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

    # Sort: points desc, then more-active first (submissions, approved),
    # then name asc. Without the activity tiebreakers a 0-point board
    # falls back to DB scan order, which made unrelated reporters appear
    # at the top of the podium for no visible reason.
    entries.sort(key=lambda e: (-e.points, -e.submissions, -e.approved, e.reporter_name))
    for i, entry in enumerate(entries, start=1):
        entry.rank = i

    return LeaderboardResponse(period=period, entries=entries)
