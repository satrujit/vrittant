"""Reviewer assignment algorithm — see docs/plans/2026-04-18-reviewer-assignment-design.md."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.story import Story
from ..models.story_assignment_log import StoryAssignmentLog
from ..models.user import User


class NoReviewersAvailable(Exception):
    """Raised when an org has zero active reviewers."""


# Stories with these statuses do NOT count toward a reviewer's open load.
_CLOSED_STATUSES = ("published", "rejected")


def _normalize(s: str | None) -> str:
    if not s:
        return ""
    out = s.strip().lower()
    if out.endswith(" district"):
        out = out[: -len(" district")].rstrip()
    return out


def _open_load(db: Session, user_id: str) -> int:
    return (
        db.query(func.count(Story.id))
        .filter(Story.assigned_to == user_id, ~Story.status.in_(_CLOSED_STATUSES))
        .scalar()
    ) or 0


def _least_loaded(db: Session, candidates: list[User]) -> User:
    """Pick the candidate with the smallest open load. Ties broken by lowest user.id."""
    scored = [(_open_load(db, u.id), u.id, u) for u in candidates]
    scored.sort(key=lambda t: (t[0], t[1]))
    return scored[0][2]


def pick_assignee(story: Story, db: Session) -> tuple[User, str]:
    """Return (reviewer, match_reason). Raises NoReviewersAvailable if org has zero reviewers."""
    reviewers = (
        db.query(User)
        .filter(
            User.organization_id == story.organization_id,
            User.user_type == "reviewer",
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .all()
    )
    if not reviewers:
        raise NoReviewersAvailable(f"No active reviewers in org {story.organization_id}")

    # Step 1 — category
    if story.category and story.category != "general":
        candidates = [r for r in reviewers if story.category in (r.categories or [])]
        if candidates:
            return _least_loaded(db, candidates), "category"

    # Step 2 — region
    reporter = story.reporter
    reporter_area = _normalize(reporter.area_name) if reporter else ""
    if reporter_area:
        candidates = [
            r for r in reviewers
            if any(_normalize(rg) == reporter_area for rg in (r.regions or []))
        ]
        if candidates:
            return _least_loaded(db, candidates), "region"

    # Step 3 — overall fallback
    return _least_loaded(db, reviewers), "load_balance"


def redistribute_open_stories(db: Session, user: User, admin_id: str) -> int:
    """Redistribute a (no-longer-eligible) reviewer's open stories to other reviewers.

    Called when an admin deactivates a reviewer or changes their role away from
    "reviewer". Open = status NOT IN ('published', 'rejected') and not soft-deleted.

    On success: updates `assigned_to` / `assigned_match_reason` and writes a
    `StoryAssignmentLog` row with reason="redistribute".

    On `NoReviewersAvailable`: nulls out `assigned_to` / `assigned_match_reason`
    on the story but skips the log row (because `StoryAssignmentLog.to_user_id`
    is non-nullable). Cleaner UX than leaving the story stuck on an inactive user.

    Caller is responsible for committing.
    """
    open_stories = (
        db.query(Story)
        .filter(
            Story.assigned_to == user.id,
            Story.organization_id == user.organization_id,
            ~Story.status.in_(_CLOSED_STATUSES),
            Story.deleted_at.is_(None),
        )
        .all()
    )
    redistributed = 0
    for story in open_stories:
        try:
            new_assignee, match_reason = pick_assignee(story, db)
        except NoReviewersAvailable:
            # No replacement available — null out the story's assignment and skip the log row.
            story.assigned_to = None
            story.assigned_match_reason = None
            continue
        story.assigned_to = new_assignee.id
        story.assigned_match_reason = match_reason
        db.add(StoryAssignmentLog(
            story_id=story.id,
            from_user_id=user.id,
            to_user_id=new_assignee.id,
            assigned_by=admin_id,
            reason="redistribute",
        ))
        redistributed += 1
    return redistributed
