# Multi-Edition Per Day Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or
> superpowers:subagent-driven-development if running in-session) to implement
> this plan task-by-task.

**Goal:** Auto-create the day's editions (6 daily + Sunday-only Avimat for
Pragativadi) and let reviewers place a story across multiple editions in one
interaction via a matrix UI.

**Architecture:** Per-org `edition_schedule` JSON config in `OrgConfig` drives
a nightly Cloud Scheduler job (`POST /internal/seed-todays-editions`) that
stamps out today's editions idempotently. A new `PUT
/admin/stories/{id}/placements` endpoint accepts the entire placement set in
one round-trip. The reviewer panel replaces the single-edition dropdown with
a matrix component that fans out by `page_name` match and shares React Query
cache keys with the bucket view for bidirectional sync.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL (Cloud SQL), React +
TanStack Query, shadcn/ui, Cloud Scheduler.

**Design doc:** `docs/plans/2026-04-25-multi-edition-design.md`

---

## Task 1: Migration — `edition_schedule` column + unique index on Edition

**Files:**
- Create: `api/migrations/2026-04-25-edition-schedule-and-unique.sql`

**Step 1:** Write the migration SQL.

```sql
-- 2026-04-25-edition-schedule-and-unique.sql
-- Adds per-org edition templates that drive the nightly auto-create
-- job, plus a uniqueness guard so the job is naturally idempotent.

ALTER TABLE org_configs
  ADD COLUMN IF NOT EXISTS edition_schedule JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Same (org, date, title) can never produce two editions. The seed
-- endpoint relies on ON CONFLICT DO NOTHING against this constraint.
CREATE UNIQUE INDEX IF NOT EXISTS uq_editions_org_date_title
  ON editions (organization_id, publication_date, title);
```

**Step 2:** Apply to UAT, then prod, via cloud-sql-proxy.

```bash
# UAT
PGPASSWORD=<uat-password> psql -h 127.0.0.1 -p 5433 -U postgres -d vrittant_uat \
  -f api/migrations/2026-04-25-edition-schedule-and-unique.sql

# Prod
PGPASSWORD=<prod-password> psql -h 127.0.0.1 -p 5433 -U postgres -d vrittant \
  -f api/migrations/2026-04-25-edition-schedule-and-unique.sql
```

Expected: `ALTER TABLE` and `CREATE UNIQUE INDEX` both succeed.

**Step 3:** Commit.

```bash
git add api/migrations/2026-04-25-edition-schedule-and-unique.sql
git commit -m "migration: edition_schedule column + unique index on editions"
```

---

## Task 2: Model — add `edition_schedule` to OrgConfig

**Files:**
- Modify: `api/app/models/org_config.py`
- Modify: `api/app/schemas/org_config.py` (if exists; else update inline schemas)

**Step 1:** Add column. Open `api/app/models/org_config.py` and add inside
the `OrgConfig` class, alongside the other JSON columns:

```python
edition_schedule = Column(JSON, nullable=False, default=list)
```

**Step 2:** Add a typed Pydantic schema for an edition template. In
`api/app/schemas/org_config.py` (or wherever OrgConfig schemas live):

```python
from pydantic import BaseModel, Field

class EditionTemplatePage(BaseModel):
    page_number: int = Field(..., ge=1, le=999)
    page_name: str = Field(..., min_length=1, max_length=64)

class EditionTemplate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    weekdays: list[int] = Field(default_factory=list)  # 0=Mon..6=Sun
    pages: list[EditionTemplatePage]
```

Reference these in the OrgConfig response/update schemas as
`edition_schedule: list[EditionTemplate]`.

**Step 3:** Run the existing OrgConfig tests to confirm nothing broke.

```bash
cd api && pytest tests/test_org_admin_config.py -v
```

Expected: all pass.

**Step 4:** Commit.

```bash
git add api/app/models/org_config.py api/app/schemas/
git commit -m "feat(orgconfig): add edition_schedule column + Pydantic types"
```

---

## Task 3: Auto-create endpoint — `POST /internal/seed-todays-editions`

**Files:**
- Modify: `api/app/routers/internal.py`
- Create: `api/tests/test_internal_seed_editions.py`

**Step 1: Write the failing tests first.**

```python
# api/tests/test_internal_seed_editions.py
"""Tests for the nightly edition-seeding endpoint."""
from datetime import date
import os
import pytest

from app.models.edition import Edition, EditionPage
from app.models.org_config import OrgConfig


PRAGATIVADI_SCHEDULE = [
    {
        "name": "Ed 1",
        "weekdays": [0, 1, 2, 3, 4, 5],
        "pages": [{"page_number": i, "page_name": f"pg_{i}"} for i in range(1, 13)],
    },
    {
        "name": "Avimat",
        "weekdays": [6],
        "pages": [{"page_number": i, "page_name": f"pg_{i}"} for i in range(1, 11)],
    },
]


@pytest.fixture
def internal_token(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "test-token")
    return "test-token"


def _set_schedule(db, org_id, schedule):
    cfg = db.query(OrgConfig).filter_by(organization_id=org_id).first()
    if not cfg:
        cfg = OrgConfig(organization_id=org_id, edition_schedule=schedule)
        db.add(cfg)
    else:
        cfg.edition_schedule = schedule
    db.commit()


def test_creates_editions_for_org_with_schedule(client, db, organization, internal_token):
    _set_schedule(db, organization.id, PRAGATIVADI_SCHEDULE)
    # Mon = weekday 0 → Ed 1 should be created, Avimat skipped.
    target = date(2026, 4, 27)  # Monday
    resp = client.post(
        "/internal/seed-todays-editions",
        headers={"X-Internal-Token": internal_token},
        json={"date": target.isoformat()},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["created"]) == 1
    eds = db.query(Edition).filter_by(organization_id=organization.id, publication_date=target).all()
    assert {e.title for e in eds} == {"Ed 1"}
    pages = db.query(EditionPage).filter_by(edition_id=eds[0].id).all()
    assert len(pages) == 12


def test_idempotent_on_repeat(client, db, organization, internal_token):
    _set_schedule(db, organization.id, PRAGATIVADI_SCHEDULE)
    target = date(2026, 4, 27)
    payload = {"date": target.isoformat()}
    headers = {"X-Internal-Token": internal_token}
    client.post("/internal/seed-todays-editions", headers=headers, json=payload)
    resp = client.post("/internal/seed-todays-editions", headers=headers, json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == []
    assert "Ed 1" in body["skipped"][0]
    eds = db.query(Edition).filter_by(organization_id=organization.id, publication_date=target).all()
    assert len(eds) == 1


def test_sunday_creates_avimat_only(client, db, organization, internal_token):
    _set_schedule(db, organization.id, PRAGATIVADI_SCHEDULE)
    target = date(2026, 4, 26)  # Sunday
    resp = client.post(
        "/internal/seed-todays-editions",
        headers={"X-Internal-Token": internal_token},
        json={"date": target.isoformat()},
    )
    assert resp.status_code == 200
    titles = {e.title for e in db.query(Edition).filter_by(publication_date=target).all()}
    assert titles == {"Avimat"}


def test_no_op_for_org_without_schedule(client, db, organization, internal_token):
    # No edition_schedule set → endpoint creates nothing for this org.
    resp = client.post(
        "/internal/seed-todays-editions",
        headers={"X-Internal-Token": internal_token},
        json={"date": "2026-04-27"},
    )
    assert resp.status_code == 200
    assert db.query(Edition).filter_by(organization_id=organization.id).count() == 0


def test_rejects_missing_token(client, db, organization):
    resp = client.post(
        "/internal/seed-todays-editions",
        json={"date": "2026-04-27"},
    )
    assert resp.status_code in (401, 403)
```

**Step 2:** Run them. They should fail (endpoint doesn't exist yet).

```bash
cd api && pytest tests/test_internal_seed_editions.py -v
```

Expected: 5 failed, "404 Not Found" or import errors.

**Step 3:** Implement the endpoint. Append to `api/app/routers/internal.py`:

```python
from datetime import date as _date
from sqlalchemy.exc import IntegrityError

from ..models.edition import Edition, EditionPage
from ..models.org_config import OrgConfig
from ..models.organization import Organization
from ..utils.tz import now_ist


@router.post("/seed-todays-editions")
async def seed_todays_editions(
    request: Request,
    db: Session = Depends(get_db),
):
    """Stamp out today's editions for every org with a non-empty
    edition_schedule. Idempotent — relies on the unique index on
    (organization_id, publication_date, title)."""
    _require_internal_token(request)
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        pass
    target = _date.fromisoformat(payload["date"]) if payload.get("date") else now_ist().date()
    weekday = target.weekday()  # Mon=0..Sun=6

    created: list[str] = []
    skipped: list[str] = []

    cfgs = db.query(OrgConfig).filter(OrgConfig.edition_schedule != None).all()  # noqa: E711
    for cfg in cfgs:
        schedule = cfg.edition_schedule or []
        for tpl in schedule:
            if weekday not in (tpl.get("weekdays") or []):
                continue
            tag = f"{cfg.organization_id}:{target}:{tpl['name']}"
            ed = Edition(
                organization_id=cfg.organization_id,
                publication_date=target,
                paper_type="daily",
                title=tpl["name"],
                status="draft",
            )
            db.add(ed)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                skipped.append(tag)
                continue
            for p in tpl.get("pages", []):
                db.add(EditionPage(
                    edition_id=ed.id,
                    page_number=p["page_number"],
                    page_name=p["page_name"],
                    sort_order=p["page_number"],
                ))
            created.append(tag)
    db.commit()
    return {"created": created, "skipped": skipped, "date": target.isoformat()}
```

If `_require_internal_token` doesn't already exist in `internal.py`, factor
it out from the existing endpoints.

**Step 4:** Run tests. All five should pass.

```bash
cd api && pytest tests/test_internal_seed_editions.py -v
```

**Step 5:** Commit.

```bash
git add api/app/routers/internal.py api/tests/test_internal_seed_editions.py
git commit -m "feat(editions): nightly auto-seed endpoint /internal/seed-todays-editions"
```

---

## Task 4: Seed Pragativadi's edition_schedule

**Files:**
- Create: `api/migrations/2026-04-25-pragativadi-edition-schedule.sql`

**Step 1:** Write the seed SQL. (Replace `<ORG_ID>` with Pragativadi's
actual organization id — find via `psql -c "SELECT id, name FROM
organizations WHERE name ILIKE '%pragativadi%';"`.)

```sql
-- 2026-04-25-pragativadi-edition-schedule.sql
-- Seeds Pragativadi with 6 daily editions + Sunday-only Avimat.
-- Editions 2-5 carry the four supplement pages pg_A..pg_D.
-- Edition 6 collapses A-D into pg_13..pg_16.

UPDATE org_configs
SET edition_schedule = '[
  {"name":"Ed 1","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"}
  ]},
  {"name":"Ed 2","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_A"},{"page_number":14,"page_name":"pg_B"},
    {"page_number":15,"page_name":"pg_C"},{"page_number":16,"page_name":"pg_D"}
  ]},
  {"name":"Ed 3","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_A"},{"page_number":14,"page_name":"pg_B"},
    {"page_number":15,"page_name":"pg_C"},{"page_number":16,"page_name":"pg_D"}
  ]},
  {"name":"Ed 4","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_A"},{"page_number":14,"page_name":"pg_B"},
    {"page_number":15,"page_name":"pg_C"},{"page_number":16,"page_name":"pg_D"}
  ]},
  {"name":"Ed 5","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_A"},{"page_number":14,"page_name":"pg_B"},
    {"page_number":15,"page_name":"pg_C"},{"page_number":16,"page_name":"pg_D"}
  ]},
  {"name":"Ed 6","weekdays":[0,1,2,3,4,5],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"},
    {"page_number":11,"page_name":"pg_11"},{"page_number":12,"page_name":"pg_12"},
    {"page_number":13,"page_name":"pg_13"},{"page_number":14,"page_name":"pg_14"},
    {"page_number":15,"page_name":"pg_15"},{"page_number":16,"page_name":"pg_16"}
  ]},
  {"name":"Avimat","weekdays":[6],"pages":[
    {"page_number":1,"page_name":"pg_1"},{"page_number":2,"page_name":"pg_2"},
    {"page_number":3,"page_name":"pg_3"},{"page_number":4,"page_name":"pg_4"},
    {"page_number":5,"page_name":"pg_5"},{"page_number":6,"page_name":"pg_6"},
    {"page_number":7,"page_name":"pg_7"},{"page_number":8,"page_name":"pg_8"},
    {"page_number":9,"page_name":"pg_9"},{"page_number":10,"page_name":"pg_10"}
  ]}
]'::jsonb
WHERE organization_id = (SELECT id FROM organizations WHERE name ILIKE '%pragativadi%' LIMIT 1);
```

**Step 2:** Apply to UAT and prod via cloud-sql-proxy (same pattern as Task 1).

Verify with: `SELECT jsonb_array_length(edition_schedule) FROM org_configs WHERE …;` → expect `7`.

**Step 3:** Commit.

```bash
git add api/migrations/2026-04-25-pragativadi-edition-schedule.sql
git commit -m "data: seed Pragativadi edition_schedule (6 daily + Avimat)"
```

---

## Task 5: Cloud Scheduler — wire up nightly trigger

**Files:** none (gcloud commands only).

**Step 1:** Create the scheduler job in both projects.

```bash
# UAT
gcloud scheduler jobs create http seed-editions-uat \
  --schedule="5 0 * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://vrittant-api-uat-pgvufpchiq-el.a.run.app/internal/seed-todays-editions" \
  --http-method=POST \
  --headers="X-Internal-Token=$(gcloud secrets versions access latest --secret=INTERNAL_TOKEN_UAT --project=vrittant-f5ef2)" \
  --location=asia-south1 \
  --project=vrittant-f5ef2

# Prod
gcloud scheduler jobs create http seed-editions-prod \
  --schedule="5 0 * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://vrittant-api-pgvufpchiq-el.a.run.app/internal/seed-todays-editions" \
  --http-method=POST \
  --headers="X-Internal-Token=$(gcloud secrets versions access latest --secret=INTERNAL_TOKEN --project=vrittant-f5ef2)" \
  --location=asia-south1 \
  --project=vrittant-f5ef2
```

**Step 2:** Trigger once manually to verify and seed today's editions if
missing:

```bash
gcloud scheduler jobs run seed-editions-uat --location=asia-south1 --project=vrittant-f5ef2
```

Then check via psql / panel that today's editions exist.

---

## Task 6: Backend — `PUT /admin/stories/{story_id}/placements`

**Files:**
- Modify: `api/app/routers/editions/write.py` (or a new placements router)
- Create: `api/tests/test_story_placements_bulk.py`

**Step 1: Write failing tests.**

```python
# api/tests/test_story_placements_bulk.py
"""Tests for the bulk placement endpoint that the matrix UI uses."""
import pytest

from app.models.edition import Edition, EditionPage, EditionPageStory


def _make_edition(db, org_id, title, page_count=12):
    ed = Edition(organization_id=org_id, publication_date="2026-04-27",
                 paper_type="daily", title=title, status="draft")
    db.add(ed); db.flush()
    pages = []
    for i in range(1, page_count + 1):
        p = EditionPage(edition_id=ed.id, page_number=i, page_name=f"pg_{i}", sort_order=i)
        db.add(p); pages.append(p)
    db.flush()
    return ed, pages


def test_inserts_new_placements(client, db, org_admin_user, organization, story):
    ed1, pages1 = _make_edition(db, organization.id, "Ed 1")
    ed2, pages2 = _make_edition(db, organization.id, "Ed 2", 16)
    db.commit()
    resp = client.put(
        f"/admin/stories/{story.id}/placements",
        headers=org_admin_user.auth_headers,
        json={"placements": [
            {"edition_id": ed1.id, "page_id": pages1[2].id},  # pg_3
            {"edition_id": ed2.id, "page_id": pages2[2].id},  # pg_3
        ]},
    )
    assert resp.status_code == 200, resp.text
    rows = db.query(EditionPageStory).filter_by(story_id=story.id).all()
    assert len(rows) == 2


def test_diffs_correctly_removes_omitted(client, db, org_admin_user, organization, story):
    ed1, pages1 = _make_edition(db, organization.id, "Ed 1")
    db.add(EditionPageStory(edition_page_id=pages1[2].id, story_id=story.id, sort_order=0))
    db.commit()
    # Send empty placement list → existing placement is removed.
    resp = client.put(
        f"/admin/stories/{story.id}/placements",
        headers=org_admin_user.auth_headers,
        json={"placements": []},
    )
    assert resp.status_code == 200
    assert db.query(EditionPageStory).filter_by(story_id=story.id).count() == 0


def test_idempotent_same_set(client, db, org_admin_user, organization, story):
    ed1, pages1 = _make_edition(db, organization.id, "Ed 1")
    db.commit()
    payload = {"placements": [{"edition_id": ed1.id, "page_id": pages1[0].id}]}
    headers = org_admin_user.auth_headers
    client.put(f"/admin/stories/{story.id}/placements", headers=headers, json=payload)
    client.put(f"/admin/stories/{story.id}/placements", headers=headers, json=payload)
    assert db.query(EditionPageStory).filter_by(story_id=story.id).count() == 1


def test_rejects_cross_org_edition(client, db, org_admin_user, other_organization, story):
    """Story belongs to org A, edition belongs to org B → reject."""
    ed_other, pages_other = _make_edition(db, other_organization.id, "Other Ed")
    db.commit()
    resp = client.put(
        f"/admin/stories/{story.id}/placements",
        headers=org_admin_user.auth_headers,
        json={"placements": [{"edition_id": ed_other.id, "page_id": pages_other[0].id}]},
    )
    assert resp.status_code in (400, 403, 404)
    assert db.query(EditionPageStory).filter_by(story_id=story.id).count() == 0
```

(Reuse existing fixtures `client`, `db`, `org_admin_user`, `organization`,
`story`. Add `other_organization` if not already defined.)

**Step 2:** Run them — should fail (404).

**Step 3:** Implement. Add to `api/app/routers/editions/write.py`:

```python
from pydantic import BaseModel
from ..stories import _load_story_for_user  # or similar existing helper

class _Placement(BaseModel):
    edition_id: str
    page_id: str

class _BulkPlacementRequest(BaseModel):
    placements: list[_Placement]


@router.put("/stories/{story_id}/placements")
def bulk_set_placements(
    story_id: str,
    body: _BulkPlacementRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
):
    """Set the full list of (edition × page) placements for a story in one
    transaction. Diffs against the current set and inserts/deletes to match."""
    story = db.query(Story).filter_by(id=story_id).first()
    if not story:
        raise HTTPException(404, "story not found")
    if story.organization_id != user.organization_id:
        raise HTTPException(403, "cross-org")

    # Validate every (edition, page) belongs to the same org and the
    # page belongs to the edition.
    desired: set[tuple[str, str]] = set()
    for p in body.placements:
        ep = (
            db.query(EditionPage)
            .join(Edition, Edition.id == EditionPage.edition_id)
            .filter(EditionPage.id == p.page_id, Edition.id == p.edition_id,
                    Edition.organization_id == user.organization_id)
            .first()
        )
        if not ep:
            raise HTTPException(400, f"invalid edition/page: {p.edition_id}/{p.page_id}")
        desired.add((p.edition_id, p.page_id))

    # Current placements for this story (across all editions of this org).
    current_rows = (
        db.query(EditionPageStory, EditionPage, Edition)
        .join(EditionPage, EditionPage.id == EditionPageStory.edition_page_id)
        .join(Edition, Edition.id == EditionPage.edition_id)
        .filter(EditionPageStory.story_id == story_id,
                Edition.organization_id == user.organization_id)
        .all()
    )
    current: set[tuple[str, str]] = {(ed.id, ep.id) for _row, ep, ed in current_rows}

    # Delete the ones no longer wanted.
    for row, ep, ed in current_rows:
        if (ed.id, ep.id) not in desired:
            db.delete(row)

    # Insert the new ones.
    for ed_id, page_id in desired - current:
        db.add(EditionPageStory(edition_page_id=page_id, story_id=story_id, sort_order=0))

    db.commit()

    # Return the canonical placement list.
    return [
        {"edition_id": ed.id, "edition_title": ed.title, "page_id": ep.id, "page_name": ep.page_name}
        for _row, ep, ed in (
            db.query(EditionPageStory, EditionPage, Edition)
            .join(EditionPage, EditionPage.id == EditionPageStory.edition_page_id)
            .join(Edition, Edition.id == EditionPage.edition_id)
            .filter(EditionPageStory.story_id == story_id,
                    Edition.organization_id == user.organization_id)
            .all()
        )
    ]
```

**Step 4:** Run tests, confirm they pass.

**Step 5:** Commit.

```bash
git add api/app/routers/editions/write.py api/tests/test_story_placements_bulk.py
git commit -m "feat(editions): bulk PUT /admin/stories/{id}/placements"
```

---

## Task 7: Backend — `GET /admin/stories/{story_id}/placements`

The matrix needs to read current placements without re-fetching the entire
story. (The bulk PUT already returns them, but the initial render needs a
GET.)

**Files:** Modify the same router file.

**Step 1:** Add a sibling GET endpoint that returns the same shape as the
bulk PUT response. Auth: same `require_reviewer`.

```python
@router.get("/stories/{story_id}/placements")
def get_placements(story_id: str, db: Session = Depends(get_db),
                    user: User = Depends(require_reviewer)):
    rows = (
        db.query(EditionPageStory, EditionPage, Edition)
        .join(EditionPage, EditionPage.id == EditionPageStory.edition_page_id)
        .join(Edition, Edition.id == EditionPage.edition_id)
        .filter(EditionPageStory.story_id == story_id,
                Edition.organization_id == user.organization_id)
        .all()
    )
    return [
        {"edition_id": ed.id, "edition_title": ed.title,
         "page_id": ep.id, "page_name": ep.page_name}
        for _row, ep, ed in rows
    ]
```

**Step 2:** Add a quick test under `test_story_placements_bulk.py` that
seeds two placements and calls the GET, asserting the response matches.

**Step 3:** Commit.

```bash
git commit -am "feat(editions): GET /admin/stories/{id}/placements"
```

---

## Task 8: Frontend — API client wrappers

**Files:**
- Modify: `reviewer-panel/src/services/api/editions.js` (add placement helpers)

**Step 1:** Add three exports.

```javascript
// reviewer-panel/src/services/api/editions.js — append

export async function getStoryPlacements(storyId) {
  const res = await api.get(`/admin/stories/${storyId}/placements`);
  return res.data;
}

export async function setStoryPlacements(storyId, placements) {
  // placements: [{edition_id, page_id}]
  const res = await api.put(`/admin/stories/${storyId}/placements`,
    { placements });
  return res.data;
}

export async function listTodaysEditions(date /* YYYY-MM-DD */) {
  // Reuses existing list endpoint with a date filter; if no date filter
  // exists yet, add one server-side OR client-filter the full list.
  const res = await api.get(`/admin/editions`, {
    params: { publication_date: date, limit: 100 },
  });
  return res.data;
}
```

If `listTodaysEditions` needs a server-side date filter that doesn't exist
yet, add one to `editions/read.py` (one-line `if publication_date:
query.filter_by(publication_date=publication_date)`). Don't gold-plate.

**Step 2:** Commit.

```bash
git add reviewer-panel/src/services/api/editions.js
git commit -m "feat(panel): editions API helpers for placements + today's list"
```

---

## Task 9: Frontend — `EditionPlacementMatrix` component

**Files:**
- Create: `reviewer-panel/src/components/review/EditionPlacementMatrix.jsx`

**Step 1:** Build the component. Skeleton:

```jsx
// reviewer-panel/src/components/review/EditionPlacementMatrix.jsx
import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getStoryPlacements,
  setStoryPlacements,
  listTodaysEditions,
} from '../../services/api/editions.js';

/**
 * Matrix UI for assigning a story across multiple editions in one shot.
 * Props:
 *   - storyId
 *   - publicationDate (YYYY-MM-DD; defaults to today's IST date)
 */
export function EditionPlacementMatrix({ storyId, publicationDate }) {
  const today = publicationDate || new Date().toISOString().slice(0, 10);
  const qc = useQueryClient();

  const editionsQ = useQuery({
    queryKey: ['editions', 'forDate', today],
    queryFn: () => listTodaysEditions(today),
  });

  const placementsQ = useQuery({
    queryKey: ['story', storyId, 'placements'],
    queryFn: () => getStoryPlacements(storyId),
    enabled: !!storyId,
  });

  // Cells the user has clicked this session — protected from fan-out.
  const [overrides, setOverrides] = useState(new Set());

  const editions = editionsQ.data?.items || editionsQ.data || [];
  const placements = placementsQ.data || [];
  // Map: edition_id -> {page_id, page_name} OR null when not placed.
  const placementByEdition = useMemo(() => {
    const m = new Map();
    for (const ed of editions) m.set(ed.id, null);
    for (const p of placements) {
      m.set(p.edition_id, { pageId: p.page_id, pageName: p.page_name });
    }
    return m;
  }, [editions, placements]);

  const mutation = useMutation({
    mutationFn: (next) => setStoryPlacements(storyId, next),
    onSuccess: (data) => {
      qc.setQueryData(['story', storyId, 'placements'], data);
      // Touched editions also need their pages cache invalidated so the
      // bucket view re-renders if open in the same tab.
      for (const ed of editions) {
        qc.invalidateQueries({ queryKey: ['edition', ed.id, 'pages'] });
      }
    },
  });

  function commit(nextMap) {
    // nextMap: Map<editionId, {pageId, pageName} | null>
    const placements = [];
    for (const [edId, val] of nextMap.entries()) {
      if (val?.pageId) placements.push({ edition_id: edId, page_id: val.pageId });
    }
    mutation.mutate(placements);
  }

  function pickPage(editionId, page) {
    const next = new Map(placementByEdition);
    next.set(editionId, page ? { pageId: page.id, pageName: page.page_name } : null);
    setOverrides(new Set(overrides).add(editionId));
    // Fan-out: every non-overridden, non-Avimat edition gets the same page_name
    if (page) {
      for (const ed of editions) {
        if (ed.id === editionId) continue;
        if (overrides.has(ed.id)) continue;
        if (ed.title === 'Avimat') continue;
        const match = ed.pages?.find((p) => p.page_name === page.page_name);
        if (match) next.set(ed.id, { pageId: match.id, pageName: match.page_name });
      }
    }
    commit(next);
  }

  function dropFromEdition(editionId) {
    const next = new Map(placementByEdition);
    next.set(editionId, null);
    setOverrides(new Set(overrides).add(editionId));
    commit(next);
  }

  function applyAllDaily() {
    // Pick the most recently chosen page_name (or pg_1) and stamp every
    // non-Avimat edition that has it.
    const ref = [...placementByEdition.values()].find((v) => v?.pageName);
    const targetName = ref?.pageName || 'pg_1';
    const next = new Map(placementByEdition);
    for (const ed of editions) {
      if (ed.title === 'Avimat') continue;
      const match = ed.pages?.find((p) => p.page_name === targetName);
      if (match) next.set(ed.id, { pageId: match.id, pageName: match.page_name });
    }
    commit(next);
  }

  function clearAll() {
    const next = new Map();
    for (const ed of editions) next.set(ed.id, null);
    commit(next);
  }

  if (editionsQ.isLoading || placementsQ.isLoading) return <div>Loading…</div>;
  if (!editions.length) return <div>No editions for {today}</div>;

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="mb-2 flex items-center gap-2">
        <button onClick={applyAllDaily}
                className="rounded-md border border-border bg-background px-2 py-0.5 text-xs hover:bg-accent">
          All daily
        </button>
        <button onClick={clearAll}
                className="rounded-md border border-border bg-background px-2 py-0.5 text-xs hover:bg-accent">
          Clear
        </button>
        {mutation.isPending && <span className="text-xs text-muted-foreground">Saving…</span>}
      </div>
      <div className="grid grid-flow-col auto-cols-min gap-1 overflow-x-auto">
        {editions.map((ed) => {
          const current = placementByEdition.get(ed.id);
          return (
            <Cell key={ed.id}
                  edition={ed}
                  current={current}
                  onPick={(p) => pickPage(ed.id, p)}
                  onDrop={() => dropFromEdition(ed.id)} />
          );
        })}
      </div>
    </div>
  );
}

function Cell({ edition, current, onPick, onDrop }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col items-center">
      <div className="text-[10px] font-medium text-muted-foreground">{edition.title}</div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="min-w-[60px] rounded border border-border bg-background px-2 py-1 text-xs hover:bg-accent"
      >
        {current?.pageName || '—'}
      </button>
      {open && (
        <div className="absolute z-50 mt-12 rounded-md border border-border bg-popover p-2 shadow">
          {edition.pages?.map((p) => (
            <button key={p.id}
                    onClick={() => { onPick(p); setOpen(false); }}
                    className="block w-full px-2 py-1 text-left text-xs hover:bg-accent">
              {p.page_name}
            </button>
          ))}
          <div className="my-1 border-t border-border" />
          <button onClick={() => { onDrop(); setOpen(false); }}
                  className="block w-full px-2 py-1 text-left text-xs text-red-500 hover:bg-red-500/10">
            Drop
          </button>
        </div>
      )}
    </div>
  );
}
```

(Style with the codebase's existing patterns; use Popover/Combobox primitives
if they exist already in `components/ui/`.)

**Step 2:** The list endpoint must return each edition's pages too. If it
doesn't yet, add `pages` to the serializer in `editions/read.py`.

**Step 3:** Commit.

```bash
git add reviewer-panel/src/components/review/EditionPlacementMatrix.jsx
git commit -m "feat(panel): EditionPlacementMatrix component"
```

---

## Task 10: Frontend — wire matrix into ReviewSidePanel

**Files:**
- Modify: `reviewer-panel/src/components/review/ReviewSidePanel.jsx`

**Step 1:** Find the existing "Choose edition…" / "Choose page…" / "Assign"
block (around lines 395–454 per the explore report). Replace with:

```jsx
import { EditionPlacementMatrix } from './EditionPlacementMatrix.jsx';

// inside the panel JSX, replacing the old single-edition dropdown:
<EditionPlacementMatrix
  storyId={story.id}
  publicationDate={story.publication_date /* or today */}
/>
```

Remove the old assign mutation and dropdown state.

**Step 2:** Update `BucketDetailPage.jsx` (or wherever the bucket view lives)
to use the same query keys for pages:

- Pages query key: `['edition', editionId, 'pages']`
- After a drag-drop mutation: also invalidate `['story', storyId,
  'placements']` so the side panel matrix re-renders.

If the keys differ today, pick the matrix's keys as canonical and migrate.

**Step 3:** Smoke-test in dev: open a story, see the matrix; click a cell;
see the placement update; open the bucket view in another tab; refresh —
placement reflects.

**Step 4:** Commit.

```bash
git add reviewer-panel/src/components/review/ReviewSidePanel.jsx \
        reviewer-panel/src/pages/BucketDetailPage.jsx
git commit -m "feat(panel): replace single-edition dropdown with matrix; share cache keys"
```

---

## Task 11: i18n — add the matrix labels in en/or/hi

**Files:**
- Modify: `reviewer-panel/src/locales/en.json`
- Modify: `reviewer-panel/src/locales/or.json`
- Modify: `reviewer-panel/src/locales/hi.json`

**Step 1:** Add a `placements` namespace with the four strings: `allDaily`,
`clear`, `drop`, `noEditions`. Mirror across all three locale files.

```json
"placements": {
  "allDaily": "All daily",
  "clear": "Clear",
  "drop": "Drop",
  "noEditions": "No editions for {{date}}"
}
```

Replace the hardcoded English in `EditionPlacementMatrix.jsx` with `t()`
calls.

**Step 2:** Commit.

```bash
git add reviewer-panel/src/locales/ reviewer-panel/src/components/review/EditionPlacementMatrix.jsx
git commit -m "i18n(panel): matrix labels in en/or/hi"
```

---

## Task 12: Build, deploy to UAT, smoke-test

**Step 1:** Build the panel.

```bash
cd reviewer-panel && npx vite build
```

Expected: clean build, no errors.

**Step 2:** Push to develop → triggers UAT deploy via GitHub Actions.

```bash
git push origin develop
```

**Step 3:** Wait for both `CI — Tests` and `Deploy to UAT` to go green.

```bash
gh run list --repo satrujit/vrittant --limit 4 --branch develop
```

If CI fails, fix tests, repush. Don't merge to main until UAT is green.

**Step 4:** Manually trigger today's edition seed in UAT (since today's
nightly already passed):

```bash
gcloud scheduler jobs run seed-editions-uat --location=asia-south1 --project=vrittant-f5ef2
```

**Step 5:** UAT smoke test (browser):
- Log in as a Pragativadi reviewer.
- Open any story.
- Confirm the right panel shows the matrix with today's editions.
- Click a cell, pick a page, watch other cells fan out.
- Click another cell to override; confirm it sticks.
- Open the bucket view; confirm the story appears on the right pages.
- Drag the story between pages in the bucket; reload the story; confirm
  the matrix reflects the new placement.

**Step 6:** Once UAT is verified, merge to main for prod.

```bash
git checkout main && git pull --rebase
git merge develop --no-edit
git push origin main
```

Watch the prod pipeline; manually trigger `seed-editions-prod` if needed
to backfill today's editions.

---

## Done

- Daily editions auto-create at 00:05 IST.
- Reviewers can place a story across multiple editions in one click.
- Bucket view and matrix stay in sync via shared cache keys.
- Capacity dot, AI suggestions, and section-aware fan-out remain in the
  v2 backlog (see design doc).
