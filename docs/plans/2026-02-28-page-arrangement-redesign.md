# Page Arrangement Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the Page Arrangement feature into a two-screen newspaper edition management system: an edition list screen and a kanban board for story arrangement.

**Architecture:** Screen 1 (`/buckets`) lists newspaper editions (date + paper type). Screen 2 (`/buckets/:editionId`) is a kanban board with a fixed unassigned panel (approved stories with filter popover) and horizontally-scrollable page columns. Backend uses 3 new SQLAlchemy tables (editions, edition_pages, edition_page_stories) with FastAPI CRUD endpoints.

**Tech Stack:** FastAPI 0.115 + SQLAlchemy 2.0 (SQLite), React 19 + react-router-dom v7, @hello-pangea/dnd, lucide-react icons, CSS Modules with `--vr-*` design tokens, i18n (en + or locales)

---

## Task 1: Backend — Edition & EditionPage Models

**Files:**
- Create: `/Users/admin/Desktop/newsflow-api/app/models/edition.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/models/__init__.py`

**Step 1: Create the Edition and EditionPage models**

Create `/Users/admin/Desktop/newsflow-api/app/models/edition.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


class Edition(Base):
    __tablename__ = "editions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    publication_date = Column(Date, nullable=False)
    paper_type = Column(String, nullable=False, default="daily")  # daily | weekend | evening | special
    title = Column(String, nullable=False, default="")
    status = Column(String, nullable=False, default="draft")  # draft | finalized | published
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    pages = relationship("EditionPage", back_populates="edition", cascade="all, delete-orphan", order_by="EditionPage.sort_order")


class EditionPage(Base):
    __tablename__ = "edition_pages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    edition_id = Column(String, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    page_name = Column(String, nullable=False, default="")
    sort_order = Column(Integer, nullable=False, default=0)

    edition = relationship("Edition", back_populates="pages")
    story_assignments = relationship("EditionPageStory", back_populates="page", cascade="all, delete-orphan", order_by="EditionPageStory.sort_order")


class EditionPageStory(Base):
    __tablename__ = "edition_page_stories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    edition_page_id = Column(String, ForeignKey("edition_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    story_id = Column(String, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order = Column(Integer, nullable=False, default=0)

    page = relationship("EditionPage", back_populates="story_assignments")
```

**Step 2: Register models in `__init__.py`**

Modify `/Users/admin/Desktop/newsflow-api/app/models/__init__.py`:

```python
from .reporter import Reporter
from .story import Story
from .edition import Edition, EditionPage, EditionPageStory

__all__ = ["Reporter", "Story", "Edition", "EditionPage", "EditionPageStory"]
```

**Step 3: Verify the server starts and tables are created**

Run: `cd /Users/admin/Desktop/newsflow-api && python -c "from app.models import Edition, EditionPage, EditionPageStory; print('Models import OK')"`

Then restart the API server. The `Base.metadata.create_all(bind=engine)` in `main.py` will auto-create the new tables.

**Step 4: Commit**

```bash
git add app/models/edition.py app/models/__init__.py
git commit -m "feat: add Edition, EditionPage, EditionPageStory models"
```

---

## Task 2: Backend — Edition Pydantic Schemas

**Files:**
- Create: `/Users/admin/Desktop/newsflow-api/app/schemas/edition.py`

**Step 1: Create edition schemas**

Create `/Users/admin/Desktop/newsflow-api/app/schemas/edition.py`:

```python
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


# ── Request schemas ──

class EditionCreate(BaseModel):
    publication_date: date
    paper_type: str = "daily"  # daily | weekend | evening | special
    title: Optional[str] = None  # auto-generated if not provided


class EditionUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class EditionPageCreate(BaseModel):
    page_name: str
    page_number: Optional[int] = None  # auto-assigned if not provided


class EditionPageUpdate(BaseModel):
    page_name: Optional[str] = None
    sort_order: Optional[int] = None


class StoryAssignmentUpdate(BaseModel):
    story_ids: list[str]  # ordered list of story IDs


# ── Response schemas ──

class EditionPageStoryResponse(BaseModel):
    id: str
    story_id: str
    sort_order: int
    model_config = {"from_attributes": True}


class EditionPageResponse(BaseModel):
    id: str
    page_number: int
    page_name: str
    sort_order: int
    story_count: int = 0
    story_assignments: list[EditionPageStoryResponse] = []
    model_config = {"from_attributes": True}


class EditionResponse(BaseModel):
    id: str
    publication_date: date
    paper_type: str
    title: str
    status: str
    page_count: int = 0
    story_count: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class EditionDetailResponse(EditionResponse):
    pages: list[EditionPageResponse] = []


class EditionListResponse(BaseModel):
    editions: list[EditionResponse]
    total: int
```

**Step 2: Commit**

```bash
git add app/schemas/edition.py
git commit -m "feat: add Pydantic schemas for editions API"
```

---

## Task 3: Backend — Editions CRUD Router

**Files:**
- Create: `/Users/admin/Desktop/newsflow-api/app/routers/editions.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/main.py`

**Step 1: Create the editions router**

Create `/Users/admin/Desktop/newsflow-api/app/routers/editions.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models.edition import Edition, EditionPage, EditionPageStory
from ..models.story import Story
from ..schemas.edition import (
    EditionCreate,
    EditionDetailResponse,
    EditionListResponse,
    EditionPageCreate,
    EditionPageResponse,
    EditionPageUpdate,
    EditionResponse,
    EditionUpdate,
    StoryAssignmentUpdate,
)

router = APIRouter(prefix="/admin/editions", tags=["editions"])

PAPER_TYPE_LABELS = {
    "daily": "Daily",
    "weekend": "Weekend",
    "evening": "Evening",
    "special": "Special",
}


def _auto_title(pub_date: date, paper_type: str) -> str:
    label = PAPER_TYPE_LABELS.get(paper_type, paper_type.title())
    return f"{label} - {pub_date.strftime('%d %b %Y')}"


def _edition_to_response(edition: Edition) -> dict:
    page_count = len(edition.pages) if edition.pages else 0
    story_count = sum(len(p.story_assignments) for p in (edition.pages or []))
    return {
        **{c.name: getattr(edition, c.name) for c in edition.__table__.columns},
        "page_count": page_count,
        "story_count": story_count,
    }


def _page_to_response(page: EditionPage) -> dict:
    return {
        **{c.name: getattr(page, c.name) for c in page.__table__.columns},
        "story_count": len(page.story_assignments) if page.story_assignments else 0,
        "story_assignments": [
            {"id": sa.id, "story_id": sa.story_id, "sort_order": sa.sort_order}
            for sa in (page.story_assignments or [])
        ],
    }


# ── Edition CRUD ──

@router.post("", status_code=status.HTTP_201_CREATED)
def create_edition(body: EditionCreate, db: Session = Depends(get_db)):
    title = body.title or _auto_title(body.publication_date, body.paper_type)
    edition = Edition(
        publication_date=body.publication_date,
        paper_type=body.paper_type,
        title=title,
    )
    db.add(edition)
    db.commit()
    db.refresh(edition)
    # Reload with pages for response
    edition = db.query(Edition).options(
        joinedload(Edition.pages).joinedload(EditionPage.story_assignments)
    ).filter(Edition.id == edition.id).first()
    return _edition_to_response(edition)


@router.get("")
def list_editions(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    total = db.query(func.count(Edition.id)).scalar()
    editions = (
        db.query(Edition)
        .options(joinedload(Edition.pages).joinedload(EditionPage.story_assignments))
        .order_by(Edition.publication_date.desc(), Edition.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    # Deduplicate (joinedload can cause dupes with multiple joins)
    seen = set()
    unique = []
    for e in editions:
        if e.id not in seen:
            seen.add(e.id)
            unique.append(e)
    return {
        "editions": [_edition_to_response(e) for e in unique],
        "total": total,
    }


@router.get("/{edition_id}")
def get_edition(edition_id: str, db: Session = Depends(get_db)):
    edition = (
        db.query(Edition)
        .options(joinedload(Edition.pages).joinedload(EditionPage.story_assignments))
        .filter(Edition.id == edition_id)
        .first()
    )
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
    resp = _edition_to_response(edition)
    resp["pages"] = [_page_to_response(p) for p in edition.pages]
    return resp


@router.put("/{edition_id}")
def update_edition(edition_id: str, body: EditionUpdate, db: Session = Depends(get_db)):
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
    if body.title is not None:
        edition.title = body.title
    if body.status is not None:
        if body.status not in ("draft", "finalized", "published"):
            raise HTTPException(status_code=400, detail="Invalid status")
        edition.status = body.status
    db.commit()
    db.refresh(edition)
    edition = db.query(Edition).options(
        joinedload(Edition.pages).joinedload(EditionPage.story_assignments)
    ).filter(Edition.id == edition.id).first()
    return _edition_to_response(edition)


@router.delete("/{edition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_edition(edition_id: str, db: Session = Depends(get_db)):
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
    db.delete(edition)
    db.commit()


# ── Edition Pages CRUD ──

@router.post("/{edition_id}/pages", status_code=status.HTTP_201_CREATED)
def add_page(edition_id: str, body: EditionPageCreate, db: Session = Depends(get_db)):
    edition = db.query(Edition).filter(Edition.id == edition_id).first()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
    # Auto page_number: max existing + 1
    max_num = (
        db.query(func.max(EditionPage.page_number))
        .filter(EditionPage.edition_id == edition_id)
        .scalar()
    ) or 0
    page_number = body.page_number if body.page_number is not None else max_num + 1
    sort_order = page_number  # default sort = page number
    page = EditionPage(
        edition_id=edition_id,
        page_number=page_number,
        page_name=body.page_name,
        sort_order=sort_order,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    page = db.query(EditionPage).options(
        joinedload(EditionPage.story_assignments)
    ).filter(EditionPage.id == page.id).first()
    return _page_to_response(page)


@router.put("/{edition_id}/pages/{page_id}")
def update_page(edition_id: str, page_id: str, body: EditionPageUpdate, db: Session = Depends(get_db)):
    page = (
        db.query(EditionPage)
        .filter(EditionPage.id == page_id, EditionPage.edition_id == edition_id)
        .first()
    )
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    if body.page_name is not None:
        page.page_name = body.page_name
    if body.sort_order is not None:
        page.sort_order = body.sort_order
    db.commit()
    db.refresh(page)
    page = db.query(EditionPage).options(
        joinedload(EditionPage.story_assignments)
    ).filter(EditionPage.id == page.id).first()
    return _page_to_response(page)


@router.delete("/{edition_id}/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page(edition_id: str, page_id: str, db: Session = Depends(get_db)):
    page = (
        db.query(EditionPage)
        .filter(EditionPage.id == page_id, EditionPage.edition_id == edition_id)
        .first()
    )
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    db.delete(page)
    db.commit()


# ── Story Assignments ──

@router.put("/{edition_id}/pages/{page_id}/stories")
def assign_stories(
    edition_id: str,
    page_id: str,
    body: StoryAssignmentUpdate,
    db: Session = Depends(get_db),
):
    page = (
        db.query(EditionPage)
        .filter(EditionPage.id == page_id, EditionPage.edition_id == edition_id)
        .first()
    )
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    # Delete existing assignments for this page
    db.query(EditionPageStory).filter(EditionPageStory.edition_page_id == page_id).delete()
    # Create new assignments in order
    for idx, story_id in enumerate(body.story_ids):
        assignment = EditionPageStory(
            edition_page_id=page_id,
            story_id=story_id,
            sort_order=idx,
        )
        db.add(assignment)
    db.commit()
    # Return updated page
    page = db.query(EditionPage).options(
        joinedload(EditionPage.story_assignments)
    ).filter(EditionPage.id == page.id).first()
    return _page_to_response(page)
```

**Step 2: Register the router in main.py**

Modify `/Users/admin/Desktop/newsflow-api/app/main.py` — add import and include:

Add to imports:
```python
from .routers import admin, auth, editions, files, sarvam, stories
```

Add after `app.include_router(admin.router)`:
```python
app.include_router(editions.router)
```

**Step 3: Restart the API server and verify**

Test: `curl http://192.168.1.7:8000/admin/editions`
Expected: `{"editions":[],"total":0}`

Test: `curl -X POST http://192.168.1.7:8000/admin/editions -H "Content-Type: application/json" -d '{"publication_date":"2026-02-28","paper_type":"daily"}'`
Expected: Returns created edition with `id`, `title: "Daily - 28 Feb 2026"`, etc.

**Step 4: Commit**

```bash
git add app/routers/editions.py app/main.py
git commit -m "feat: add editions CRUD API endpoints"
```

---

## Task 4: Frontend — API Service Functions for Editions

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/services/api.js`

**Step 1: Add edition API functions**

Append to the end of `api.js` (before the closing of the file, after `transformReporter`):

```javascript
// ── Editions API ──

export async function fetchEditions(params = {}) {
  const query = buildQuery(params);
  return apiFetch(`/admin/editions${query}`);
}

export async function fetchEdition(id) {
  return apiFetch(`/admin/editions/${id}`);
}

export async function createEdition(data) {
  return apiFetch('/admin/editions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateEdition(id, data) {
  return apiFetch(`/admin/editions/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteEdition(id) {
  return apiFetch(`/admin/editions/${id}`, { method: 'DELETE' });
}

export async function addEditionPage(editionId, data) {
  return apiFetch(`/admin/editions/${editionId}/pages`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateEditionPage(editionId, pageId, data) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteEditionPage(editionId, pageId) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}`, {
    method: 'DELETE',
  });
}

export async function assignStoriesToPage(editionId, pageId, storyIds) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}/stories`, {
    method: 'PUT',
    body: JSON.stringify({ story_ids: storyIds }),
  });
}
```

**Step 2: Commit**

```bash
git add src/services/api.js
git commit -m "feat: add edition API service functions"
```

---

## Task 5: Frontend — i18n Translations for Editions

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/i18n/locales/en.json`
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/i18n/locales/or.json`

**Step 1: Update the `buckets` section in `en.json`**

Replace the existing `"buckets"` block with:

```json
"buckets": {
  "title": "Page Arrangement",
  "subtitle": "Create newspaper editions and arrange approved stories across pages.",
  "newEdition": "+ New Edition",
  "editionTitle": "Edition",
  "publicationDate": "Publication Date",
  "paperType": "Paper Type",
  "paperTypes": {
    "daily": "Daily",
    "weekend": "Weekend",
    "evening": "Evening",
    "special": "Special"
  },
  "editionStatus": {
    "draft": "Draft",
    "finalized": "Finalized",
    "published": "Published"
  },
  "pages": "pages",
  "stories": "stories",
  "noEditions": "No editions yet. Create one to get started.",
  "deleteEdition": "Delete Edition",
  "deleteEditionConfirm": "Are you sure? This will remove all page assignments.",
  "createEditionTitle": "Create New Edition",
  "create": "Create",
  "cancel": "Cancel",
  "backToEditions": "Back to Editions",
  "newPage": "+ Add Page",
  "addPageTitle": "Add Page",
  "pageName": "Page Name",
  "pageNamePlaceholder": "e.g. Front Page",
  "pageSuggestions": "Suggestions:",
  "searchPlaceholder": "Search stories...",
  "empty": "No stories on this page.",
  "unassigned": "Unassigned",
  "unassignedDesc": "Approved stories not yet placed on a page",
  "filterTitle": "Filter Stories",
  "filterByCategory": "Category",
  "filterByLocation": "Location",
  "clearFilters": "Clear All",
  "applyFilters": "Apply",
  "allCategories": "All Categories",
  "allLocations": "All Locations"
}
```

**Step 2: Update the `buckets` section in `or.json`**

Replace the existing `"buckets"` block with:

```json
"buckets": {
  "title": "ପୃଷ୍ଠା ବିନ୍ୟାସ",
  "subtitle": "ସମ୍ବାଦପତ୍ର ସଂସ୍କରଣ ତିଆରି କରନ୍ତୁ ଏବଂ ଅନୁମୋଦିତ ଖବର ସଜାନ୍ତୁ।",
  "newEdition": "+ ନୂଆ ସଂସ୍କରଣ",
  "editionTitle": "ସଂସ୍କରଣ",
  "publicationDate": "ପ୍ରକାଶନ ତାରିଖ",
  "paperType": "କାଗଜ ପ୍ରକାର",
  "paperTypes": {
    "daily": "ଦୈନିକ",
    "weekend": "ସପ୍ତାହାନ୍ତ",
    "evening": "ସନ୍ଧ୍ୟା",
    "special": "ବିଶେଷ"
  },
  "editionStatus": {
    "draft": "ଡ୍ରାଫ୍ଟ",
    "finalized": "ସଂପୂର୍ଣ୍ଣ",
    "published": "ପ୍ରକାଶିତ"
  },
  "pages": "ପୃଷ୍ଠା",
  "stories": "ଖବର",
  "noEditions": "ଏପର୍ଯ୍ୟନ୍ତ କୌଣସି ସଂସ୍କରଣ ନାହିଁ। ଆରମ୍ଭ କରିବାକୁ ଗୋଟିଏ ତିଆରି କରନ୍ତୁ।",
  "deleteEdition": "ସଂସ୍କରଣ ବିଲୋପ",
  "deleteEditionConfirm": "ନିଶ୍ଚିତ? ସବୁ ପୃଷ୍ଠା ଆସାଇନମେଣ୍ଟ ହଟାଇ ଦିଆଯିବ।",
  "createEditionTitle": "ନୂଆ ସଂସ୍କରଣ ତିଆରି",
  "create": "ତିଆରି",
  "cancel": "ବାତିଲ",
  "backToEditions": "ସଂସ୍କରଣ ତାଲିକାକୁ ଫେରନ୍ତୁ",
  "newPage": "+ ନୂଆ ପୃଷ୍ଠା",
  "addPageTitle": "ପୃଷ୍ଠା ଯୋଡ଼ନ୍ତୁ",
  "pageName": "ପୃଷ୍ଠା ନାମ",
  "pageNamePlaceholder": "ଉଦା. ପ୍ରଥମ ପୃଷ୍ଠା",
  "pageSuggestions": "ସୁପାରିଶ:",
  "searchPlaceholder": "ଖବର ଖୋଜନ୍ତୁ...",
  "empty": "ଏହି ପୃଷ୍ଠାରେ କୌଣସି ଖବର ନାହିଁ।",
  "unassigned": "ଅନିର୍ଦ୍ଧାରିତ",
  "unassignedDesc": "ପୃଷ୍ଠାରେ ସ୍ଥାନ ନ ପାଇଥିବା ଅନୁମୋଦିତ ଖବର",
  "filterTitle": "ଖବର ଫିଲ୍ଟର",
  "filterByCategory": "ବିଭାଗ",
  "filterByLocation": "ସ୍ଥାନ",
  "clearFilters": "ସବୁ ସଫା",
  "applyFilters": "ଲାଗୁ",
  "allCategories": "ସବୁ ବିଭାଗ",
  "allLocations": "ସବୁ ସ୍ଥାନ"
}
```

**Step 3: Commit**

```bash
git add src/i18n/locales/en.json src/i18n/locales/or.json
git commit -m "feat: update i18n translations for edition management"
```

---

## Task 6: Frontend — Edition List Page (Screen 1)

**Files:**
- Create: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/EditionsPage.jsx`
- Create: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/EditionsPage.module.css`

**Step 1: Create EditionsPage component**

This is the edition list/grid screen at `/buckets`. Shows existing editions as cards, with a "+ New Edition" button that opens a Modal for creating a new edition (date picker + paper type dropdown). Clicking a card navigates to `/buckets/:editionId`.

Key behavior:
- On mount, `fetchEditions()` to load all editions
- "+ New Edition" button opens the shared `Modal` component
- Modal contains: date input (`type="date"`), paper type `<select>` with 4 options (daily/weekend/evening/special), and Create/Cancel buttons
- On create, calls `createEdition({ publication_date, paper_type })`, then refreshes list
- Each edition card shows: title, publication_date (formatted), paper_type badge, status badge, page count, story count
- Delete button on each card (with confirmation) calls `deleteEdition(id)`
- Click on card → `navigate(\`/buckets/${edition.id}\`)`

Use CSS Modules with `var(--vr-*)` tokens. Grid layout for cards (auto-fill, min 300px columns). Follow the same import patterns as other pages (useI18n, lucide icons, etc.).

**Step 2: Create EditionsPage.module.css**

Kanban-free layout. Simple grid of edition cards. Same design token usage as other pages. Key classes: `.page`, `.header`, `.grid`, `.editionCard`, `.cardTitle`, `.badge`, `.meta`, `.deleteBtn`, `.formGroup`, `.formLabel`, `.formInput`, `.formSelect`, `.formActions`.

**Step 3: Commit**

```bash
git add src/pages/EditionsPage.jsx src/pages/EditionsPage.module.css
git commit -m "feat: add EditionsPage (edition list screen)"
```

---

## Task 7: Frontend — Kanban Board Page (Screen 2)

**Files:**
- Rewrite: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/BucketsPage.jsx`
- Rewrite: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/BucketsPage.module.css`

**Step 1: Rewrite BucketsPage as the kanban board for a specific edition**

This is the kanban board at `/buckets/:editionId`. It fetches the edition details + approved stories, and shows:

**Header:**
- Back arrow (`ArrowLeft` icon) → navigates to `/buckets`
- Edition title (editable inline, calls `updateEdition` on save)
- "+ Add Page" button → opens a small popover/modal with page name input + suggestion chips

**Page Name Suggestions** (hardcoded array):
```javascript
const PAGE_SUGGESTIONS = [
  'Front Page', 'State News', 'National News', 'International',
  'Sports', 'Entertainment', 'Business', 'Editorial', 'Classifieds',
];
```

**Left Panel (fixed, 300px):** Unassigned column
- Shows approved stories NOT assigned to any page in this edition
- Filter icon button in the header → opens a floating popover
- Filter popover: category checkboxes + location checkboxes (populated from available stories)
- Cards are draggable (use `@hello-pangea/dnd`)

**Right Area (horizontal scroll):** Page columns
- Each column = one `EditionPage`
- Header: "Page {n} — {name}" (editable on pencil click), delete button
- Droppable area for story cards
- Stories within a page can be reordered via drag

**Data flow:**
- On mount: `fetchEdition(editionId)` → get pages + story assignments
- On mount: `fetchStories({ status: 'approved', limit: 500 })` → get all approved stories
- Compute unassigned = approved stories whose IDs are NOT in any page's assignments
- On drag end: update local state, then call `assignStoriesToPage(editionId, pageId, storyIds)` for affected pages
- On add page: call `addEditionPage(editionId, { page_name })`, refresh
- On delete page: call `deleteEditionPage(editionId, pageId)`, refresh (stories return to unassigned)
- On rename page: call `updateEditionPage(editionId, pageId, { page_name })`

**Layout rules:**
- `.page { height: 100%; overflow: hidden; }` — no vertical scroll
- Unassigned panel: fixed left, vertical scroll within card list
- Pages area: horizontal scroll only, each column has vertical scroll within card list

**Step 2: Rewrite BucketsPage.module.css**

Same structure as current CSS but refined for the new layout. Key additions:
- `.filterBtn` — filter icon button on unassigned header
- `.filterPopover` — floating popover positioned below the filter button
- `.filterSection` — category/location sections within popover
- `.filterCheckbox` — checkbox + label rows
- `.filterActions` — Apply/Clear buttons
- `.addPagePopover` — suggestion chips + text input for page name
- `.suggestionChip` — clickable chip for each page name suggestion
- `.backBtn` — back arrow button in header

**Step 3: Commit**

```bash
git add src/pages/BucketsPage.jsx src/pages/BucketsPage.module.css
git commit -m "feat: rewrite BucketsPage as edition kanban board"
```

---

## Task 8: Frontend — Routing Update

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/App.jsx`

**Step 1: Add the new route and import**

Update `App.jsx`:
- Import `EditionsPage` from `./pages/EditionsPage`
- Change `/buckets` route to render `EditionsPage`
- Add new route `/buckets/:editionId` to render `BucketsPage`

```jsx
import EditionsPage from './pages/EditionsPage';
// BucketsPage import stays

// Inside Routes:
<Route path="/buckets" element={<EditionsPage />} />
<Route path="/buckets/:editionId" element={<BucketsPage />} />
```

Both routes remain inside the `<AppLayout>` wrapper (sidebar visible).

**Step 2: Commit**

```bash
git add src/App.jsx
git commit -m "feat: add /buckets/:editionId route for kanban board"
```

---

## Task 9: Integration Test — Full Flow Verification

**Step 1: Restart the FastAPI backend**

Ensure the new tables are created and endpoints respond.

**Step 2: Open the app at `http://localhost:5174/buckets`**

Verify:
- Edition list page loads with empty state message
- Click "+ New Edition" → modal opens
- Select a date and paper type → create → edition card appears
- Click the edition card → navigates to `/buckets/:editionId`
- Kanban board loads with unassigned stories on left
- Click "+ Add Page" → page name suggestions appear
- Click "Front Page" → new page column appears
- Drag a story from unassigned → page column → story appears in page
- Filter icon on unassigned → popover with category checkboxes
- Back arrow → returns to edition list
- Delete edition → edition removed

**Step 3: Commit any fixes discovered during testing**

```bash
git add -A
git commit -m "fix: integration fixes for edition management flow"
```

---

## Summary

| Task | Description | Backend | Frontend |
|------|-------------|---------|----------|
| 1 | SQLAlchemy models (Edition, EditionPage, EditionPageStory) | Yes | — |
| 2 | Pydantic schemas for API request/response | Yes | — |
| 3 | FastAPI CRUD router for editions | Yes | — |
| 4 | API service functions in api.js | — | Yes |
| 5 | i18n translations (en + or) | — | Yes |
| 6 | EditionsPage — edition list screen | — | Yes |
| 7 | BucketsPage — kanban board rewrite | — | Yes |
| 8 | Routing update in App.jsx | — | Yes |
| 9 | Integration testing | Both | Both |
