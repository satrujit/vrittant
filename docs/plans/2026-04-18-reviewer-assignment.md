# Reviewer Assignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Auto-assign every newly submitted story to a specific reviewer based on category and region beats, with one-click reassignment, full audit log, and least-loaded tie-breaking.

**Architecture:** Pure `pick_assignee()` function called synchronously at story-submit time and at reviewer-deactivation time. Three-step funnel: category match → region match → overall least-loaded. New `assigned_to` column on `stories`, new `categories`/`regions` JSON columns on `users`, new `story_assignment_log` audit table. Frontend gets an inline dropdown in the stories list, a match-reason badge, and a filter (`Assigned to me` default).

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2 + Alembic-style raw SQL via cloud-sql-proxy (Cloud Run); React + Vite + Tailwind 4 + shadcn/ui; pytest backend, vitest frontend.

**Reference:** Design doc — `docs/plans/2026-04-18-reviewer-assignment-design.md`.

---

## Pre-flight

Before any code: confirm we're on `develop` branch, in a clean worktree, and that prod DB has no reporters with empty `area_name` (per design Section 5).

```bash
cd /Users/admin/Desktop/vrittant-monorepo
git status              # expect clean
git branch              # expect develop
```

For the prod-data check, defer until the migration task — we'll run it then with cloud-sql-proxy.

---

## Task 1 — Add `categories` and `regions` JSON columns to User model

**Files:**
- Modify: `api/app/models/user.py`
- Test: `api/tests/test_user_model_beats.py` (create)

**Step 1: Write the failing test**

```python
# api/tests/test_user_model_beats.py
"""User model has categories and regions JSON columns for reviewer beats."""
from app.models.user import User


def test_user_has_categories_default_empty_list():
    u = User(name="A", phone="1")
    assert u.categories == [] or u.categories is None  # default applied at flush


def test_user_has_regions_default_empty_list():
    u = User(name="A", phone="1")
    assert u.regions == [] or u.regions is None
```

**Step 2: Run test to verify it fails**

```bash
cd api && python -m pytest tests/test_user_model_beats.py -v
```
Expected: FAIL with `AttributeError: 'User' object has no attribute 'categories'`.

**Step 3: Add columns to User model**

Edit `api/app/models/user.py`. Add `JSON` to the SQLAlchemy import. After `area_name` add:

```python
    categories = Column(JSON, nullable=False, default=list)  # reviewer beats
    regions = Column(JSON, nullable=False, default=list)     # reviewer beats
```

Final import line:
```python
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
```

**Step 4: Run test to verify it passes**

```bash
cd api && python -m pytest tests/test_user_model_beats.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add api/app/models/user.py api/tests/test_user_model_beats.py
git commit -m "feat(user): add categories and regions JSON columns for reviewer beats"
```

---

## Task 2 — Add `assigned_to` and `assigned_match_reason` to Story model

**Files:**
- Modify: `api/app/models/story.py`
- Test: `api/tests/test_story_model_assignment.py` (create)

**Step 1: Write the failing test**

```python
# api/tests/test_story_model_assignment.py
from app.models.story import Story


def test_story_has_assigned_to_column():
    s = Story(reporter_id="r", organization_id="o")
    assert hasattr(s, "assigned_to")


def test_story_has_assigned_match_reason_column():
    s = Story(reporter_id="r", organization_id="o")
    assert hasattr(s, "assigned_match_reason")
```

**Step 2: Run test to verify it fails**

```bash
cd api && python -m pytest tests/test_story_model_assignment.py -v
```
Expected: FAIL — attributes missing.

**Step 3: Add columns**

Edit `api/app/models/story.py`. After the `reviewed_at` line add:

```python
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    assigned_match_reason = Column(String, nullable=True)  # category | region | load_balance | manual
```

And in the relationships block, after `reviewer = ...` add:

```python
    assignee = relationship("User", foreign_keys=[assigned_to])
```

**Step 4: Run test to verify it passes**

```bash
cd api && python -m pytest tests/test_story_model_assignment.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add api/app/models/story.py api/tests/test_story_model_assignment.py
git commit -m "feat(story): add assigned_to and assigned_match_reason columns"
```

---

## Task 3 — Create StoryAssignmentLog model

**Files:**
- Create: `api/app/models/story_assignment_log.py`
- Modify: `api/app/models/__init__.py` (if it explicitly imports models — check)
- Test: `api/tests/test_story_assignment_log_model.py` (create)

**Step 1: Write the failing test**

```python
# api/tests/test_story_assignment_log_model.py
from app.models.story_assignment_log import StoryAssignmentLog


def test_log_columns():
    log = StoryAssignmentLog(
        story_id="s", from_user_id=None, to_user_id="u",
        assigned_by=None, reason="auto",
    )
    assert log.story_id == "s"
    assert log.from_user_id is None
    assert log.to_user_id == "u"
    assert log.assigned_by is None
    assert log.reason == "auto"
```

**Step 2: Run test to verify it fails**

```bash
cd api && python -m pytest tests/test_story_assignment_log_model.py -v
```
Expected: FAIL — module not found.

**Step 3: Create the model**

```python
# api/app/models/story_assignment_log.py
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String

from ..database import Base
from ..utils.tz import now_ist


class StoryAssignmentLog(Base):
    __tablename__ = "story_assignment_log"
    __table_args__ = (
        Index("ix_story_assignment_log_story_id", "story_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id = Column(String, ForeignKey("stories.id"), nullable=False)
    from_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    to_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    assigned_by = Column(String, ForeignKey("users.id"), nullable=True)  # null = system
    reason = Column(String, nullable=False)  # auto | manual | reviewer_deactivated
    created_at = Column(DateTime, default=now_ist, nullable=False)
```

If `api/app/models/__init__.py` exists with explicit imports, add `from .story_assignment_log import StoryAssignmentLog`. Check first:

```bash
cat api/app/models/__init__.py
```

**Step 4: Run test to verify it passes**

```bash
cd api && python -m pytest tests/test_story_assignment_log_model.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add api/app/models/story_assignment_log.py api/tests/test_story_assignment_log_model.py api/app/models/__init__.py
git commit -m "feat: add StoryAssignmentLog model for audit trail"
```

---

## Task 4 — Implement `pick_assignee()` algorithm

**Files:**
- Create: `api/app/services/assignment.py`
- Test: `api/tests/test_assignment_algorithm.py` (create)

**Step 1: Write the failing tests**

```python
# api/tests/test_assignment_algorithm.py
"""Unit tests for pick_assignee — three-step funnel + tie-breaking."""
import pytest
from sqlalchemy.orm import Session

from app.models.story import Story
from app.models.user import User
from app.services.assignment import pick_assignee, NoReviewersAvailable


def _make_user(db, *, name, user_type="reviewer", area="", categories=None, regions=None, active=True):
    u = User(
        name=name, phone=name, user_type=user_type, area_name=area,
        organization_id="org1", organization="Org",
        categories=categories or [], regions=regions or [], is_active=active,
    )
    db.add(u); db.commit(); db.refresh(u)
    return u


def _make_story(db, *, reporter, category=None):
    s = Story(reporter_id=reporter.id, organization_id="org1", category=category, paragraphs=[])
    db.add(s); db.commit(); db.refresh(s)
    return s


def test_category_match_picks_only_matching_reviewer(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="Koraput")
    sports = _make_user(db, name="sportsr", categories=["sports"])
    politics = _make_user(db, name="politicsr", categories=["politics"])
    story = _make_story(db, reporter=reporter, category="sports")

    user, reason = pick_assignee(story, db)
    assert user.id == sports.id
    assert reason == "category"


def test_category_match_least_loaded_among_candidates(db):
    reporter = _make_user(db, name="rep", user_type="reporter")
    a = _make_user(db, name="a", categories=["sports"])
    b = _make_user(db, name="b", categories=["sports"])
    # Give a one open story already
    db.add(Story(reporter_id=reporter.id, organization_id="org1",
                 assigned_to=a.id, status="submitted", paragraphs=[])); db.commit()
    story = _make_story(db, reporter=reporter, category="sports")

    user, reason = pick_assignee(story, db)
    assert user.id == b.id  # least loaded


def test_general_category_skips_step_1(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="Koraput")
    _make_user(db, name="sportsr", categories=["sports"])
    region_match = _make_user(db, name="kor", regions=["Koraput"])
    story = _make_story(db, reporter=reporter, category="general")

    user, reason = pick_assignee(story, db)
    assert user.id == region_match.id
    assert reason == "region"


def test_null_category_skips_step_1(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="Koraput")
    region_match = _make_user(db, name="kor", regions=["Koraput"])
    story = _make_story(db, reporter=reporter, category=None)

    user, reason = pick_assignee(story, db)
    assert user.id == region_match.id
    assert reason == "region"


def test_region_match_normalized(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="  KORAPUT District ")
    region_match = _make_user(db, name="kor", regions=["koraput"])
    story = _make_story(db, reporter=reporter)

    user, reason = pick_assignee(story, db)
    assert user.id == region_match.id
    assert reason == "region"


def test_overall_fallback_when_no_match(db):
    reporter = _make_user(db, name="rep", user_type="reporter", area="Cuttack")
    a = _make_user(db, name="a", categories=["politics"])
    b = _make_user(db, name="b", regions=["Bhubaneswar"])
    story = _make_story(db, reporter=reporter, category="sports")

    user, reason = pick_assignee(story, db)
    assert user.id in (a.id, b.id)
    assert reason == "load_balance"


def test_inactive_reviewer_excluded(db):
    reporter = _make_user(db, name="rep", user_type="reporter")
    inactive = _make_user(db, name="i", categories=["sports"], active=False)
    active = _make_user(db, name="a", categories=["sports"])
    story = _make_story(db, reporter=reporter, category="sports")

    user, _ = pick_assignee(story, db)
    assert user.id == active.id


def test_no_reviewers_raises(db):
    reporter = _make_user(db, name="rep", user_type="reporter")
    story = _make_story(db, reporter=reporter, category="sports")

    with pytest.raises(NoReviewersAvailable):
        pick_assignee(story, db)


def test_tie_breaks_on_lowest_user_id(db):
    reporter = _make_user(db, name="rep", user_type="reporter")
    # IDs are random uuids — pick whichever sorts lower
    a = _make_user(db, name="a", categories=["sports"])
    b = _make_user(db, name="b", categories=["sports"])
    expected_id = min(a.id, b.id)
    story = _make_story(db, reporter=reporter, category="sports")

    user, _ = pick_assignee(story, db)
    assert user.id == expected_id
```

`db` fixture should already exist from `api/tests/conftest.py`. Open it to confirm:

```bash
cat api/tests/conftest.py
```

If no `db` fixture exists, copy the pattern from one of the existing tests like `test_org_admin_users.py`.

**Step 2: Run tests to verify they fail**

```bash
cd api && python -m pytest tests/test_assignment_algorithm.py -v
```
Expected: ALL FAIL — `app.services.assignment` doesn't exist yet.

**Step 3: Create the service**

```python
# api/app/services/assignment.py
"""Reviewer assignment algorithm — see docs/plans/2026-04-18-reviewer-assignment-design.md."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.story import Story
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
```

**Step 4: Run tests to verify they pass**

```bash
cd api && python -m pytest tests/test_assignment_algorithm.py -v
```
Expected: ALL PASS.

**Step 5: Commit**

```bash
git add api/app/services/assignment.py api/tests/test_assignment_algorithm.py
git commit -m "feat: implement pick_assignee algorithm with category/region/load-balance funnel"
```

---

## Task 5 — Hook auto-assignment into reporter story-submit

The reporter flow is two endpoints: `POST /stories` (create as draft) and `POST /stories/{id}/submit` (transition draft → submitted). Per design Section 2, **assign at submit time** — when the story actually enters the review queue.

**Files:**
- Modify: `api/app/routers/stories.py:119-137` (the `submit_story` endpoint)
- Test: `api/tests/test_submit_story_assignment.py` (create)

**Step 1: Write the failing test**

```python
# api/tests/test_submit_story_assignment.py
"""Submitting a story auto-assigns it to a reviewer and writes an audit log row."""
from app.models.story import Story
from app.models.story_assignment_log import StoryAssignmentLog


def test_submit_assigns_to_matching_reviewer(client_authed_reporter, reviewer_user, draft_story):
    resp = client_authed_reporter.post(f"/stories/{draft_story.id}/submit")
    assert resp.status_code == 200
    body = resp.json()
    # Story now has an assignee
    assert body.get("assigned_to") == reviewer_user.id  # if API exposes it
    # Or verify via DB if not in response


def test_submit_writes_assignment_log(db, client_authed_reporter, reviewer_user, draft_story):
    client_authed_reporter.post(f"/stories/{draft_story.id}/submit")
    log = db.query(StoryAssignmentLog).filter(StoryAssignmentLog.story_id == draft_story.id).first()
    assert log is not None
    assert log.from_user_id is None      # first auto-assign
    assert log.to_user_id == reviewer_user.id
    assert log.assigned_by is None       # system
    assert log.reason == "auto"


def test_submit_no_reviewers_succeeds_with_null_assignee(db, client_authed_reporter, draft_story):
    """Submit must not 500 if org has zero reviewers — story stays unassigned."""
    resp = client_authed_reporter.post(f"/stories/{draft_story.id}/submit")
    assert resp.status_code == 200
    s = db.query(Story).filter(Story.id == draft_story.id).first()
    assert s.status == "submitted"
    assert s.assigned_to is None
```

Build the fixtures `client_authed_reporter`, `reviewer_user`, `draft_story` in `conftest.py` if not already present. Pattern: see existing tests that create a User + JWT + Story.

**Step 2: Run tests to verify they fail**

```bash
cd api && python -m pytest tests/test_submit_story_assignment.py -v
```
Expected: FAIL — assignment not happening yet.

**Step 3: Modify `submit_story`**

Edit `api/app/routers/stories.py`. Replace the body of `submit_story` (lines 119-137) with:

```python
@router.post("/{story_id}/submit", response_model=StoryResponse)
def submit_story(
    story_id: str,
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
    db: Session = Depends(get_db),
):
    from ..services.assignment import pick_assignee, NoReviewersAvailable
    from ..models.story_assignment_log import StoryAssignmentLog

    story = db.query(Story).filter(
        Story.id == story_id, Story.reporter_id == user.id,
        Story.organization_id == org_id, Story.deleted_at.is_(None)
    ).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    if story.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafts can be submitted")

    story.status = "submitted"
    story.submitted_at = now_ist()
    story.updated_at = now_ist()

    # Auto-assign to a reviewer (graceful no-op if zero reviewers).
    try:
        reviewer, reason = pick_assignee(story, db)
        story.assigned_to = reviewer.id
        story.assigned_match_reason = reason
        db.add(StoryAssignmentLog(
            story_id=story.id, from_user_id=None, to_user_id=reviewer.id,
            assigned_by=None, reason="auto",
        ))
    except NoReviewersAvailable:
        pass  # story is submitted but unassigned; admin will see banner

    db.commit()
    db.refresh(story)
    return story
```

Also add `assigned_to` and `assigned_match_reason` to `StoryResponse` schema. Check `api/app/schemas/story.py`:

```bash
grep -n "class StoryResponse" api/app/schemas/story.py
```

Add the two new optional fields there.

**Step 4: Run tests to verify they pass**

```bash
cd api && python -m pytest tests/test_submit_story_assignment.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add api/app/routers/stories.py api/app/schemas/story.py api/tests/test_submit_story_assignment.py api/tests/conftest.py
git commit -m "feat(stories): auto-assign reviewer on submit + write audit log"
```

---

## Task 6 — Add `PATCH /admin/stories/{id}/assignee` endpoint

**Files:**
- Modify: `api/app/routers/admin/stories.py` (append new endpoint)
- Test: `api/tests/test_admin_assignee_endpoint.py` (create)

**Step 1: Write the failing test**

```python
# api/tests/test_admin_assignee_endpoint.py
from app.models.story_assignment_log import StoryAssignmentLog


def test_reassign_updates_story(db, client_authed_reviewer, story_assigned_to_a, reviewer_b):
    resp = client_authed_reviewer.patch(
        f"/admin/stories/{story_assigned_to_a.id}/assignee",
        json={"assignee_id": reviewer_b.id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assigned_to"] == reviewer_b.id
    assert body["assigned_match_reason"] == "manual"


def test_reassign_writes_log(db, client_authed_reviewer, story_assigned_to_a, reviewer_b, current_reviewer):
    client_authed_reviewer.patch(
        f"/admin/stories/{story_assigned_to_a.id}/assignee",
        json={"assignee_id": reviewer_b.id},
    )
    log = (db.query(StoryAssignmentLog)
           .filter(StoryAssignmentLog.story_id == story_assigned_to_a.id, StoryAssignmentLog.reason == "manual")
           .first())
    assert log.from_user_id == story_assigned_to_a.assigned_to or log.from_user_id is not None
    assert log.to_user_id == reviewer_b.id
    assert log.assigned_by == current_reviewer.id


def test_reassign_rejects_non_reviewer_assignee(client_authed_reviewer, story_assigned_to_a, reporter_user):
    resp = client_authed_reviewer.patch(
        f"/admin/stories/{story_assigned_to_a.id}/assignee",
        json={"assignee_id": reporter_user.id},
    )
    assert resp.status_code == 400


def test_reassign_404_for_missing_story(client_authed_reviewer, reviewer_b):
    resp = client_authed_reviewer.patch(
        "/admin/stories/nonexistent/assignee",
        json={"assignee_id": reviewer_b.id},
    )
    assert resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

```bash
cd api && python -m pytest tests/test_admin_assignee_endpoint.py -v
```
Expected: FAIL — endpoint missing.

**Step 3: Implement the endpoint**

Append to `api/app/routers/admin/stories.py`:

```python
# ---------------------------------------------------------------------------
# PATCH /admin/stories/{story_id}/assignee  (any reviewer or admin)
# ---------------------------------------------------------------------------

class ReassignRequest(BaseModel):
    assignee_id: str


@router.patch("/stories/{story_id}/assignee", response_model=AdminStoryResponse)
def admin_reassign_story(
    story_id: str,
    body: ReassignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    from ...models.story_assignment_log import StoryAssignmentLog

    story = (
        db.query(Story).options(joinedload(Story.reporter), joinedload(Story.reviewer))
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    new_assignee = (
        db.query(User)
        .filter(User.id == body.assignee_id, User.organization_id == org_id,
                User.user_type == "reviewer", User.is_active.is_(True), User.deleted_at.is_(None))
        .first()
    )
    if not new_assignee:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Assignee must be an active reviewer in this organization")

    previous = story.assigned_to
    story.assigned_to = new_assignee.id
    story.assigned_match_reason = "manual"
    story.updated_at = now_ist()
    db.add(StoryAssignmentLog(
        story_id=story.id, from_user_id=previous, to_user_id=new_assignee.id,
        assigned_by=user.id, reason="manual",
    ))
    db.commit()
    db.refresh(story)
    resp = AdminStoryResponse.model_validate(story)
    resp.reviewer_name = story.reviewer.name if story.reviewer else None
    return resp
```

Also add `assigned_to`, `assigned_match_reason`, and `assignee_name` to the relevant Pydantic schemas in `_shared.py` — `AdminStoryResponse`, `AdminStoryListItem`, `AdminStoryWithRevisionResponse`. Pattern (apply to all three):

```python
    assigned_to: Optional[str] = None
    assignee_name: Optional[str] = None
    assigned_match_reason: Optional[str] = None
```

And in the list-builder loop (`api/app/routers/admin/stories.py:88-108` and `:138-156`) populate them:

```python
            assigned_to=s.assigned_to,
            assignee_name=s.assignee.name if s.assignee else None,
            assigned_match_reason=s.assigned_match_reason,
```

Add `joinedload(Story.assignee)` to the query options in those two list functions, and to the get/update endpoints too.

**Step 4: Run tests to verify they pass**

```bash
cd api && python -m pytest tests/test_admin_assignee_endpoint.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add api/app/routers/admin/stories.py api/app/routers/admin/_shared.py api/tests/test_admin_assignee_endpoint.py
git commit -m "feat(admin): add PATCH /admin/stories/{id}/assignee + expose assignment in list/detail"
```

---

## Task 7 — Add `assigned_to` filter to `GET /admin/stories`

**Files:**
- Modify: `api/app/routers/admin/stories.py` (the `admin_list_stories` function)
- Modify: `api/app/routers/admin/_shared.py:_build_story_query` (add param)
- Test: `api/tests/test_admin_assigned_to_filter.py` (create)

**Step 1: Write the failing test**

```python
# api/tests/test_admin_assigned_to_filter.py
def test_filter_assigned_to_me(client_authed_reviewer, current_reviewer, story_assigned_to_me, story_assigned_to_other):
    resp = client_authed_reviewer.get("/admin/stories?assigned_to=me")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()["stories"]]
    assert story_assigned_to_me.id in ids
    assert story_assigned_to_other.id not in ids


def test_filter_assigned_to_specific_user(client_authed_reviewer, reviewer_b, story_assigned_to_other):
    resp = client_authed_reviewer.get(f"/admin/stories?assigned_to={reviewer_b.id}")
    ids = [s["id"] for s in resp.json()["stories"]]
    assert story_assigned_to_other.id in ids


def test_filter_omitted_returns_all(client_authed_reviewer, story_assigned_to_me, story_assigned_to_other):
    resp = client_authed_reviewer.get("/admin/stories")
    ids = [s["id"] for s in resp.json()["stories"]]
    assert story_assigned_to_me.id in ids
    assert story_assigned_to_other.id in ids
```

**Step 2: Run tests to verify they fail**

```bash
cd api && python -m pytest tests/test_admin_assigned_to_filter.py -v
```
Expected: FAIL — filter doesn't exist.

**Step 3: Add the filter**

In `_build_story_query` add a new kwarg `assigned_to: Optional[str] = None` and apply:

```python
    if assigned_to:
        query = query.filter(Story.assigned_to == assigned_to)
```

In `admin_list_stories` add:

```python
    assigned_to: Optional[str] = Query(None, description="Filter by assignee user_id, or 'me'"),
```

Resolve `me`:

```python
    resolved_assigned = user.id if assigned_to == "me" else assigned_to
```

Pass `assigned_to=resolved_assigned` into `_build_story_query`. Apply the same in the delta-mode branch.

**Step 4: Run tests to verify they pass**

```bash
cd api && python -m pytest tests/test_admin_assigned_to_filter.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add api/app/routers/admin/stories.py api/app/routers/admin/_shared.py api/tests/test_admin_assigned_to_filter.py
git commit -m "feat(admin): add assigned_to filter to GET /admin/stories (supports 'me')"
```

---

## Task 8 — Add `GET /admin/stories/{id}/assignment-log` endpoint

**Files:**
- Modify: `api/app/routers/admin/stories.py` (append)
- Test: `api/tests/test_assignment_log_endpoint.py` (create)

**Step 1: Write the failing test**

```python
# api/tests/test_assignment_log_endpoint.py
def test_log_returns_history_newest_first(client_authed_reviewer, story_with_two_assignments):
    resp = client_authed_reviewer.get(f"/admin/stories/{story_with_two_assignments.id}/assignment-log")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 2
    # Newest first
    assert rows[0]["created_at"] >= rows[1]["created_at"]


def test_log_404_for_missing_story(client_authed_reviewer):
    resp = client_authed_reviewer.get("/admin/stories/nonexistent/assignment-log")
    assert resp.status_code == 404
```

**Step 2: Run to verify failure**

```bash
cd api && python -m pytest tests/test_assignment_log_endpoint.py -v
```
Expected: FAIL.

**Step 3: Implement endpoint**

Append to `api/app/routers/admin/stories.py`:

```python
class AssignmentLogEntry(BaseModel):
    id: str
    from_user_id: Optional[str]
    from_user_name: Optional[str]
    to_user_id: str
    to_user_name: Optional[str]
    assigned_by: Optional[str]
    assigned_by_name: Optional[str]
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/stories/{story_id}/assignment-log", response_model=list[AssignmentLogEntry])
def admin_assignment_log(
    story_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    from ...models.story_assignment_log import StoryAssignmentLog

    story = db.query(Story).filter(
        Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None)
    ).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    rows = (
        db.query(StoryAssignmentLog)
        .filter(StoryAssignmentLog.story_id == story_id)
        .order_by(StoryAssignmentLog.created_at.desc())
        .all()
    )
    # Hydrate names in one query
    user_ids = {r.from_user_id for r in rows} | {r.to_user_id for r in rows} | {r.assigned_by for r in rows}
    user_ids.discard(None)
    name_map = {u.id: u.name for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    return [
        AssignmentLogEntry(
            id=r.id, from_user_id=r.from_user_id, from_user_name=name_map.get(r.from_user_id),
            to_user_id=r.to_user_id, to_user_name=name_map.get(r.to_user_id),
            assigned_by=r.assigned_by, assigned_by_name=name_map.get(r.assigned_by),
            reason=r.reason, created_at=r.created_at,
        )
        for r in rows
    ]
```

**Step 4: Run to verify pass**

```bash
cd api && python -m pytest tests/test_assignment_log_endpoint.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add api/app/routers/admin/stories.py api/tests/test_assignment_log_endpoint.py
git commit -m "feat(admin): add GET /admin/stories/{id}/assignment-log"
```

---

## Task 9 — Extend admin user CRUD: categories, regions, required area_name

**Files:**
- Modify: `api/app/schemas/org_admin.py` (`CreateUserRequest`, `UpdateUserRequest`, `UserManagementResponse`)
- Modify: `api/app/routers/admin/users.py` (`create_user`, `update_user`)
- Modify: `api/app/models/org_config.py` (no change — already has `categories`)
- Test: `api/tests/test_admin_user_beats.py` (create)

**Step 1: Write the failing test**

```python
# api/tests/test_admin_user_beats.py
def test_create_reviewer_with_beats(client_authed_admin, org_with_categories):
    resp = client_authed_admin.post("/admin/users", json={
        "name": "R", "phone": "9999999991", "user_type": "reviewer",
        "area_name": "", "categories": ["sports"], "regions": ["Koraput"],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["categories"] == ["sports"]
    assert body["regions"] == ["Koraput"]


def test_update_reviewer_beats(client_authed_admin, reviewer_b):
    resp = client_authed_admin.put(f"/admin/users/{reviewer_b.id}", json={
        "categories": ["politics", "sports"], "regions": ["Cuttack"],
    })
    assert resp.status_code == 200
    assert set(resp.json()["categories"]) == {"politics", "sports"}


def test_reject_unknown_category(client_authed_admin, reviewer_b):
    resp = client_authed_admin.put(f"/admin/users/{reviewer_b.id}", json={
        "categories": ["not-a-real-category"],
    })
    assert resp.status_code == 400


def test_create_reporter_requires_area_name(client_authed_admin):
    resp = client_authed_admin.post("/admin/users", json={
        "name": "R", "phone": "9999999992", "user_type": "reporter",
        "area_name": "",
    })
    assert resp.status_code == 400


def test_update_reporter_blank_area_rejected(client_authed_admin, reporter_user):
    resp = client_authed_admin.put(f"/admin/users/{reporter_user.id}", json={
        "area_name": "  ",
    })
    assert resp.status_code == 400
```

**Step 2: Run to verify failure**

```bash
cd api && python -m pytest tests/test_admin_user_beats.py -v
```

**Step 3: Update schemas and routes**

Edit `api/app/schemas/org_admin.py` — add `categories` and `regions` to `CreateUserRequest`, `UpdateUserRequest`, and `UserManagementResponse`:

```python
    categories: Optional[list[str]] = None
    regions: Optional[list[str]] = None
```

(Default `None` = "leave unchanged" semantics for update.)

In `api/app/routers/admin/users.py`:

```python
from ...models.org_config import OrgConfig

def _validate_categories(db, org_id, categories):
    cfg = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    valid_keys = {c["key"] for c in (cfg.categories if cfg else [])}
    bad = [c for c in categories if c not in valid_keys]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown categories: {bad}")

def _require_area_for_reporter(user_type, area_name):
    if user_type == "reporter" and (not area_name or not area_name.strip()):
        raise HTTPException(status_code=400, detail="Reporters must have a non-empty area_name")
```

In `create_user`, before `db.add(user)`:
```python
    _require_area_for_reporter(body.user_type, body.area_name)
    if body.user_type == "reviewer" and body.categories:
        _validate_categories(db, org_id, body.categories)
    user.categories = body.categories or []
    user.regions = body.regions or []
```

In `update_user`, before `db.commit()`:
```python
    if body.categories is not None:
        if user.user_type == "reviewer":
            _validate_categories(db, org_id, body.categories)
        user.categories = body.categories
    if body.regions is not None:
        user.regions = body.regions
    if body.area_name is not None and user.user_type == "reporter":
        if not body.area_name.strip():
            raise HTTPException(status_code=400, detail="Reporters must have a non-empty area_name")
```

Update `UserManagementResponse` builders in both endpoints to include `categories=user.categories or []`, `regions=user.regions or []`.

**Step 4: Run to verify pass**

```bash
cd api && python -m pytest tests/test_admin_user_beats.py -v
```

**Step 5: Commit**

```bash
git add api/app/schemas/org_admin.py api/app/routers/admin/users.py api/tests/test_admin_user_beats.py
git commit -m "feat(admin/users): manage reviewer categories/regions; require reporter area"
```

---

## Task 10 — Reviewer deactivation redistributes open stories

**Files:**
- Modify: `api/app/routers/admin/users.py:update_user` (deactivation path) — when `is_active` flips false, redistribute.
- Test: `api/tests/test_reviewer_deactivation_redistribute.py` (create)

**Step 1: Write the failing test**

```python
# api/tests/test_reviewer_deactivation_redistribute.py
from app.models.story import Story
from app.models.story_assignment_log import StoryAssignmentLog


def test_deactivating_reviewer_redistributes_open_stories(
    db, client_authed_admin, reviewer_a_with_3_open, reviewer_b_active
):
    resp = client_authed_admin.put(f"/admin/users/{reviewer_a_with_3_open.id}", json={"is_active": False})
    assert resp.status_code == 200

    open_stories = db.query(Story).filter(Story.assigned_to == reviewer_a_with_3_open.id).all()
    assert open_stories == []  # reassigned away

    log_count = (
        db.query(StoryAssignmentLog)
        .filter(StoryAssignmentLog.reason == "reviewer_deactivated")
        .count()
    )
    assert log_count == 3
```

**Step 2: Run to verify failure**

```bash
cd api && python -m pytest tests/test_reviewer_deactivation_redistribute.py -v
```

**Step 3: Implement redistribution**

In `api/app/routers/admin/users.py:update_user`, replace the `is_active` handling:

```python
    if body.is_active is not None:
        was_active = user.is_active
        user.is_active = body.is_active
        if was_active and not body.is_active and user.user_type == "reviewer":
            _redistribute_open_stories(db, user, org_id)
```

Add helper:

```python
from ...services.assignment import pick_assignee, NoReviewersAvailable
from ...models.story import Story
from ...models.story_assignment_log import StoryAssignmentLog
from sqlalchemy.orm import joinedload

_REDIST_OPEN_STATUSES = ("submitted", "in_progress", "approved")  # not published/rejected/draft

def _redistribute_open_stories(db, deactivated_user, org_id):
    open_stories = (
        db.query(Story)
        .options(joinedload(Story.reporter))
        .filter(
            Story.assigned_to == deactivated_user.id,
            Story.organization_id == org_id,
            Story.status.in_(_REDIST_OPEN_STATUSES),
            Story.deleted_at.is_(None),
        )
        .all()
    )
    # Flush is_active=False FIRST so pick_assignee excludes this user
    db.flush()
    for s in open_stories:
        try:
            new_reviewer, reason = pick_assignee(s, db)
            db.add(StoryAssignmentLog(
                story_id=s.id, from_user_id=deactivated_user.id, to_user_id=new_reviewer.id,
                assigned_by=None, reason="reviewer_deactivated",
            ))
            s.assigned_to = new_reviewer.id
            s.assigned_match_reason = reason
        except NoReviewersAvailable:
            s.assigned_to = None
            s.assigned_match_reason = None
```

**Step 4: Run to verify pass**

```bash
cd api && python -m pytest tests/test_reviewer_deactivation_redistribute.py -v
```

**Step 5: Commit**

```bash
git add api/app/routers/admin/users.py api/tests/test_reviewer_deactivation_redistribute.py
git commit -m "feat(admin/users): redistribute open stories on reviewer deactivation"
```

---

## Task 11 — Run full backend test suite

```bash
cd api && python -m pytest -x -q
```
Expected: ALL PASS. If any pre-existing tests broke (e.g. response shape changed because of new fields), update them surgically — do not weaken assertions.

```bash
git status   # likely clean if nothing changed
```

If you fixed pre-existing tests, commit:
```bash
git commit -am "test: update fixtures for new assignment fields"
```

---

## Task 12 — Frontend: API client functions

**Files:**
- Modify: `reviewer-panel/src/services/api/stories.js` (or wherever admin stories live — check)
- Modify: `reviewer-panel/src/services/api/users.js`
- Test: `reviewer-panel/src/test/assignment-api.test.js` (create)

Locate first:
```bash
ls reviewer-panel/src/services/api/
grep -l "admin/stories" reviewer-panel/src/services/api/*.js
```

**Step 1: Write the failing test**

```js
// reviewer-panel/src/test/assignment-api.test.js
import { describe, it, expect, vi } from 'vitest';
import { reassignStory, fetchAssignmentLog } from '../services/api/stories';

describe('assignment API', () => {
  it('reassignStory PATCHes the right URL with assignee_id body', async () => {
    const mock = vi.fn(() => Promise.resolve({ id: 's1', assigned_to: 'u2' }));
    global.fetch = vi.fn((url, opts) => {
      mock(url, opts);
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ id: 's1', assigned_to: 'u2' }) });
    });
    const r = await reassignStory('s1', 'u2');
    expect(r.assigned_to).toBe('u2');
    expect(mock).toHaveBeenCalledWith(
      expect.stringContaining('/admin/stories/s1/assignee'),
      expect.objectContaining({ method: 'PATCH' })
    );
  });
});
```

**Step 2: Run to verify failure**
```bash
cd reviewer-panel && npx vitest run src/test/assignment-api.test.js
```

**Step 3: Add API functions**

In the existing admin-stories service file (use `apiPatch`/`apiGet` from `../http.js`):

```js
export async function reassignStory(storyId, assigneeId) {
  return apiPatch(`/admin/stories/${storyId}/assignee`, { assignee_id: assigneeId });
}

export async function fetchAssignmentLog(storyId) {
  return apiGet(`/admin/stories/${storyId}/assignment-log`);
}
```

If `apiPatch` doesn't exist in `http.js`, add it (mirror `apiPost`).

In the users service, add `fetchActiveReviewers()`:
```js
export async function fetchActiveReviewers() {
  return apiGet('/admin/users?role=reviewer&active=true');
}
```

(Confirm the existing users endpoint supports those query params; if not, add the filter in `api/app/routers/admin/users.py` first — small follow-up TDD pass.)

**Step 4: Run to verify pass**
```bash
cd reviewer-panel && npx vitest run src/test/assignment-api.test.js
```

**Step 5: Commit**
```bash
git add reviewer-panel/src/services/api/ reviewer-panel/src/test/assignment-api.test.js
git commit -m "feat(api): add reassignStory, fetchAssignmentLog, fetchActiveReviewers"
```

---

## Task 13 — Frontend: i18n keys

**Files:**
- Modify: `reviewer-panel/src/i18n/locales/en.json`
- Modify: `reviewer-panel/src/i18n/locales/or.json`
- Modify: `reviewer-panel/src/i18n/locales/hi.json`

Add (under appropriate top-level groups, mirror existing structure):

```json
{
  "assignment": {
    "assignedToMe": "Assigned to me",
    "allReviewers": "All",
    "reasonCategory": "Category match",
    "reasonRegion": "Region match",
    "reasonLoadBalance": "Load balance",
    "reasonManual": "Manual",
    "reassignSuccess": "Reassigned",
    "history": "Assignment history",
    "deactivateConfirm": "This will redistribute {{count}} open stories to other reviewers. Continue?"
  },
  "userForm": {
    "categoriesLabel": "Categories",
    "regionsLabel": "Regions",
    "areaRequired": "Area is required for reporters"
  }
}
```

Translate to Odia (`or.json`) and Hindi (`hi.json`).

**Commit:**
```bash
git add reviewer-panel/src/i18n/locales/
git commit -m "i18n: add reviewer assignment + user-form keys"
```

---

## Task 14 — Frontend: assignee column + inline dropdown in stories list

**Files:**
- Modify: `reviewer-panel/src/pages/AllStoriesPage.jsx` (and/or `DashboardPage.jsx` — wherever the list renders)
- Possibly create: `reviewer-panel/src/components/common/AssigneePicker.jsx`

**Plan:**

1. Build a new component `AssigneePicker` that takes `{ storyId, currentAssigneeId, currentAssigneeName, reviewers, matchReason, onChange }`. Renders a small shadcn `Select` with reviewer options + a muted badge below showing the match reason.
2. On change → optimistically update local state, call `reassignStory(storyId, newId)`, show toast on success/error (rollback on error).
3. Plug it into the stories list as a new column.

**Step 1: Write a smoke test**
```js
// reviewer-panel/src/test/assignee-picker.test.jsx
import { render, fireEvent } from '@testing-library/react';
import AssigneePicker from '../components/common/AssigneePicker';

it('calls onChange with new id when user picks', async () => {
  const onChange = vi.fn();
  const { getByRole } = render(<AssigneePicker
    storyId="s1" currentAssigneeId="u1"
    reviewers={[{id:'u1',name:'A'},{id:'u2',name:'B'}]}
    matchReason="category" onChange={onChange}
  />);
  // ... interaction depends on shadcn Select; use userEvent
});
```

**Step 2-4:** Implement, render, test. Pull match-reason label from i18n (`assignment.reasonCategory` etc.).

**Step 5:** Commit.
```bash
git add reviewer-panel/src/components/common/AssigneePicker.jsx \
        reviewer-panel/src/pages/AllStoriesPage.jsx \
        reviewer-panel/src/test/assignee-picker.test.jsx
git commit -m "feat(stories): inline assignee picker with match-reason badge"
```

---

## Task 15 — Frontend: assignee filter (`Assigned to me` / picker / `All`)

**Files:**
- Modify: `reviewer-panel/src/pages/AllStoriesPage.jsx`

Add a `Select` next to existing filters with options:
- `me` (default) → label `t('assignment.assignedToMe')`
- each reviewer name → value = `reviewer.id`
- `all` → label `t('assignment.allReviewers')`

Persist to URL via `useSearchParams` (`?assigned_to=me|<id>|all`). Default to `me` on first load when param absent. When fetching the list, pass `assigned_to=<value>` unless value is `all` (then omit).

**Commit:**
```bash
git commit -am "feat(stories): assignee filter with URL persistence (default: me)"
```

---

## Task 16 — Frontend: review-page header assignee picker + history drawer

**Files:**
- Modify: `reviewer-panel/src/pages/ReviewPage.jsx`
- Possibly create: `reviewer-panel/src/components/review/AssignmentHistoryDrawer.jsx`

1. Render `<AssigneePicker>` in the review-page header.
2. Add a small "Assignment history" button that opens a drawer/sheet listing entries from `fetchAssignmentLog(storyId)` as a vertical timeline.

**Commit:**
```bash
git add reviewer-panel/src/pages/ReviewPage.jsx reviewer-panel/src/components/review/AssignmentHistoryDrawer.jsx
git commit -m "feat(review): header assignee picker + assignment history drawer"
```

---

## Task 17 — Frontend: SettingsPage user form — categories, regions, required area

**Files:**
- Modify: `reviewer-panel/src/pages/SettingsPage.jsx` (or whichever file holds the user edit form — search if needed)
- Possibly modify: `reviewer-panel/src/components/settings/UserForm.jsx`

1. When `user_type === 'reviewer'`, render two new fields below entitlements:
   - **Categories** — multi-select chips, options from `OrgConfig.categories` (already fetched somewhere; reuse).
   - **Regions** — free-text tag input (Enter adds, Backspace removes).
2. When `user_type === 'reporter'`, add a red asterisk to `area_name` and validate non-empty on submit (block save with inline error).
3. On save, include `categories`/`regions` in the PUT body when reviewer; the existing payload covers the rest.
4. On reviewer deactivation (toggling `is_active` off), pop a confirm modal showing approximate open-story count (use a small `GET /admin/stories?assigned_to=<id>&status=submitted` to count, or accept the design's simpler text without count — your call).

**Commit:**
```bash
git commit -am "feat(settings): manage reviewer beats + enforce reporter area + deactivation confirm"
```

---

## Task 18 — Frontend: full test run + build

```bash
cd reviewer-panel
npx vitest run
npx vite build
```
Expected: tests PASS, build succeeds with no new warnings.

---

## Task 19 — DB migration (production)

@superpowers:verification-before-completion — verify exact migration script before applying.

**Step 1: Pre-flight reporter `area_name` check**

Spin up cloud-sql-proxy (in a separate terminal) per `docs/infra.md`. Then:

```bash
psql "host=127.0.0.1 port=5432 user=... dbname=..." -c "
SELECT id, name, area_name FROM users
WHERE user_type='reporter' AND (area_name IS NULL OR TRIM(area_name)='');
"
```

Expected: zero rows. If any rows, **stop**, surface to the user, fix in the admin UI first.

**Step 2: Apply migration**

Save and run:

```sql
-- Save as: api/migrations/2026-04-18-reviewer-assignment.sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS categories JSON NOT NULL DEFAULT '[]';
ALTER TABLE users ADD COLUMN IF NOT EXISTS regions JSON NOT NULL DEFAULT '[]';
ALTER TABLE stories ADD COLUMN IF NOT EXISTS assigned_to VARCHAR REFERENCES users(id);
ALTER TABLE stories ADD COLUMN IF NOT EXISTS assigned_match_reason VARCHAR;
CREATE INDEX IF NOT EXISTS ix_stories_assigned_to ON stories(assigned_to);

CREATE TABLE IF NOT EXISTS story_assignment_log (
  id VARCHAR PRIMARY KEY,
  story_id VARCHAR NOT NULL REFERENCES stories(id),
  from_user_id VARCHAR REFERENCES users(id),
  to_user_id VARCHAR NOT NULL REFERENCES users(id),
  assigned_by VARCHAR REFERENCES users(id),
  reason VARCHAR NOT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_story_assignment_log_story_id ON story_assignment_log(story_id);

-- Enforce reporter area_name (only after pre-flight returned zero)
ALTER TABLE users ALTER COLUMN area_name SET NOT NULL;
```

```bash
psql "..." -f api/migrations/2026-04-18-reviewer-assignment.sql
```

Verify:

```bash
psql "..." -c "\d users"
psql "..." -c "\d stories"
psql "..." -c "\d story_assignment_log"
```

**Commit the migration script (DB change is already live):**
```bash
git add api/migrations/2026-04-18-reviewer-assignment.sql
git commit -m "chore(db): migration for reviewer assignment"
```

---

## Task 20 — Deploy backend

```bash
cd /Users/admin/Desktop/vrittant-monorepo
gcloud run deploy vrittant-api --source . --region asia-south1 --project vrittant-f5ef2 --allow-unauthenticated
```

Smoke:
```bash
curl -s "https://vrittant-api-829303072442.asia-south1.run.app/health" | head
```

---

## Task 21 — Admin one-time setup

Tell the user (it's a manual UI step):

> Open the admin Settings page → for each reviewer, set their **Categories** and **Regions**. This is a one-time setup before the new logic takes effect. Existing stories are all already approved per your earlier note, so no backfill is needed.

---

## Task 22 — Deploy frontend

```bash
cd /Users/admin/Desktop/vrittant-monorepo/reviewer-panel
npx vite build
npx firebase deploy --only hosting
```

---

## Task 23 — End-to-end smoke

1. As a reporter (mobile or test user): file a new story under category `sports` from area `Koraput`.
2. As a reviewer with `categories=["sports"]`: open the dashboard with default filter (`Assigned to me`) — confirm the story appears with badge `📂 Sports`.
3. Reassign it via the inline dropdown to another reviewer — confirm toast, dashboard updates, and the row vanishes from "me".
4. Open the new assignee's review page → click "Assignment history" → confirm two entries (auto + manual) newest-first.
5. Toggle a reviewer to inactive in admin Settings → confirm any open stories assigned to them get redistributed.

Document any deviations and address before considering complete.

---

## Task 24 — Finishing

@superpowers:finishing-a-development-branch — merge `develop` → `main`, push.

```bash
git checkout main
git merge --ff-only develop
git push origin main
git checkout develop
git push origin develop
```
