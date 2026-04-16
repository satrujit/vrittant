# Story Revisions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce a `story_revisions` table so editor edits are stored separately from the reporter's original submission, preserving both versions.

**Architecture:** New `StoryRevision` SQLAlchemy model with UNIQUE constraint on `story_id`. The `PUT /admin/stories/{id}` endpoint upserts into `story_revisions` instead of overwriting the `stories` table. The `GET` endpoints include revision data in responses. Frontend loads revision content into the editor when present.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2.0 (SQLite), Pydantic v2, pytest, React (Vite)

---

### Task 1: Set Up Test Infrastructure

There are no tests in this project yet. We need a minimal pytest setup with an in-memory SQLite database.

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create requirements-dev.txt**

```
pytest==8.3.3
httpx==0.27.2
```

**Step 2: Install dev dependencies**

Run: `cd /Users/admin/Desktop/newsflow-api && pip install -r requirements-dev.txt`
Expected: Successfully installed pytest

**Step 3: Create test infrastructure**

Create `tests/__init__.py` (empty file).

Create `tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from jose import jwt

from app.database import Base, get_db
from app.config import settings
from app.main import app
from app.models.user import User
from app.models.story import Story


@pytest.fixture()
def db():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    """TestClient that uses the test database."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def reviewer(db):
    """Create and return a reviewer user."""
    user = User(
        id="reviewer-1",
        name="Test Reviewer",
        phone="+911111111111",
        user_type="reviewer",
        organization="Test Org",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def reporter(db):
    """Create and return a reporter user."""
    user = User(
        id="reporter-1",
        name="Test Reporter",
        phone="+912222222222",
        user_type="reporter",
        area_name="Test Area",
        organization="Test Org",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def sample_story(db, reporter):
    """Create and return a submitted story."""
    story = Story(
        id="story-1",
        reporter_id=reporter.id,
        headline="Original Headline",
        category="politics",
        paragraphs=[{"id": "p1", "text": "Original paragraph one."}, {"id": "p2", "text": "Original paragraph two."}],
        status="submitted",
    )
    db.add(story)
    db.commit()
    return story


@pytest.fixture()
def auth_header(reviewer):
    """JWT Authorization header for the reviewer."""
    token = jwt.encode({"sub": reviewer.id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}
```

**Step 4: Verify test infrastructure works**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/ -v --co`
Expected: "no tests ran" (collected 0 items) — no errors

**Step 5: Commit**

```bash
git add requirements-dev.txt tests/
git commit -m "chore: add pytest test infrastructure with in-memory SQLite"
```

---

### Task 2: Create StoryRevision Model

**Files:**
- Create: `tests/test_story_revision_model.py`
- Create: `app/models/story_revision.py`
- Modify: `app/main.py` (import so table is created)

**Step 1: Write the failing test**

Create `tests/test_story_revision_model.py`:

```python
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.story_revision import StoryRevision


def test_create_story_revision(db, sample_story, reviewer):
    revision = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Edited Headline",
        paragraphs=[{"id": "p1", "text": "Edited paragraph."}],
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)

    assert revision.id is not None
    assert revision.story_id == sample_story.id
    assert revision.editor_id == reviewer.id
    assert revision.headline == "Edited Headline"
    assert revision.paragraphs == [{"id": "p1", "text": "Edited paragraph."}]
    assert revision.created_at is not None
    assert revision.updated_at is not None


def test_unique_constraint_one_revision_per_story(db, sample_story, reviewer):
    r1 = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="First edit",
        paragraphs=[],
    )
    db.add(r1)
    db.commit()

    r2 = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Second edit",
        paragraphs=[],
    )
    db.add(r2)
    with pytest.raises(IntegrityError):
        db.commit()


def test_revision_story_relationship(db, sample_story, reviewer):
    revision = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Edited",
        paragraphs=[],
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)

    assert revision.story is not None
    assert revision.story.id == sample_story.id
    assert revision.editor is not None
    assert revision.editor.id == reviewer.id
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_story_revision_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.story_revision'`

**Step 3: Write the model**

Create `app/models/story_revision.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database import Base


class StoryRevision(Base):
    __tablename__ = "story_revisions"
    __table_args__ = (
        UniqueConstraint("story_id", name="uq_story_revisions_story_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id = Column(String, ForeignKey("stories.id"), nullable=False, index=True)
    editor_id = Column(String, ForeignKey("users.id"), nullable=False)
    headline = Column(String, nullable=False)
    paragraphs = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    story = relationship("Story", back_populates="revision")
    editor = relationship("User")
```

**Step 4: Add back-reference on Story model**

Add to `app/models/story.py`, after the existing `reporter` relationship:

```python
    revision = relationship("StoryRevision", back_populates="story", uselist=False)
```

**Step 5: Import model in main.py so the table is auto-created**

Add to `app/main.py` imports:

```python
from .routers import admin, auth, editions, files, sarvam, stories
```

Change to:

```python
from .routers import admin, auth, editions, files, sarvam, stories
from .models.story_revision import StoryRevision  # noqa: F401 — ensure table is created
```

**Step 6: Run tests to verify they pass**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_story_revision_model.py -v`
Expected: 3 passed

**Step 7: Commit**

```bash
git add app/models/story_revision.py app/models/story.py app/main.py tests/test_story_revision_model.py
git commit -m "feat: add StoryRevision model with unique story_id constraint"
```

---

### Task 3: Add Pydantic Schemas for Revision

**Files:**
- Create: `tests/test_revision_schemas.py`
- Modify: `app/schemas/story.py`

**Step 1: Write the failing test**

Create `tests/test_revision_schemas.py`:

```python
from app.schemas.story import RevisionResponse


def test_revision_response_schema():
    data = {
        "id": "rev-1",
        "story_id": "story-1",
        "editor_id": "reviewer-1",
        "headline": "Edited",
        "paragraphs": [{"id": "p1", "text": "edited text"}],
        "created_at": "2026-02-28T10:00:00",
        "updated_at": "2026-02-28T10:00:00",
    }
    r = RevisionResponse(**data)
    assert r.id == "rev-1"
    assert r.headline == "Edited"
    assert len(r.paragraphs) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_revision_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'RevisionResponse'`

**Step 3: Add schemas to app/schemas/story.py**

Add at the end of `app/schemas/story.py`:

```python
class RevisionResponse(BaseModel):
    id: str
    story_id: str
    editor_id: str
    headline: str
    paragraphs: list[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_revision_schemas.py -v`
Expected: 1 passed

**Step 5: Commit**

```bash
git add app/schemas/story.py tests/test_revision_schemas.py
git commit -m "feat: add RevisionResponse Pydantic schema"
```

---

### Task 4: Modify PUT /admin/stories/{id} to Upsert Revision

This is the core change. Instead of overwriting the story, the endpoint now upserts into `story_revisions`.

**Files:**
- Create: `tests/test_admin_revision_endpoints.py`
- Modify: `app/routers/admin.py`

**Step 1: Write the failing tests**

Create `tests/test_admin_revision_endpoints.py`:

```python
"""Tests for story revision upsert via PUT /admin/stories/{id}."""


def test_put_creates_revision_on_first_save(client, auth_header, sample_story, db):
    """First PUT should INSERT a new revision row."""
    resp = client.put(
        f"/admin/stories/{sample_story.id}",
        json={
            "headline": "Editor Headline",
            "paragraphs": [{"id": "p1", "text": "Editor text"}],
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Revision should be present in response
    assert data["revision"] is not None
    assert data["revision"]["headline"] == "Editor Headline"
    assert data["revision"]["paragraphs"] == [{"id": "p1", "text": "Editor text"}]

    # Original story should be unchanged
    assert data["headline"] == "Original Headline"
    assert data["paragraphs"] == [
        {"id": "p1", "text": "Original paragraph one."},
        {"id": "p2", "text": "Original paragraph two."},
    ]


def test_put_updates_existing_revision(client, auth_header, sample_story):
    """Second PUT should UPDATE the existing revision row, not create a new one."""
    # First save
    client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "First edit", "paragraphs": [{"id": "p1", "text": "v1"}]},
        headers=auth_header,
    )
    # Second save
    resp = client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Second edit", "paragraphs": [{"id": "p1", "text": "v2"}]},
        headers=auth_header,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["revision"]["headline"] == "Second edit"
    assert data["revision"]["paragraphs"] == [{"id": "p1", "text": "v2"}]


def test_put_story_not_found(client, auth_header):
    resp = client.put(
        "/admin/stories/nonexistent",
        json={"headline": "x", "paragraphs": []},
        headers=auth_header,
    )
    assert resp.status_code == 404


def test_put_preserves_original_story_immutably(client, auth_header, sample_story, db):
    """After PUT, stories table should remain unchanged."""
    from app.models.story import Story

    client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Totally new headline", "paragraphs": [{"id": "p1", "text": "new"}]},
        headers=auth_header,
    )

    db.expire_all()
    story = db.query(Story).filter(Story.id == sample_story.id).first()
    assert story.headline == "Original Headline"
    assert story.paragraphs == [
        {"id": "p1", "text": "Original paragraph one."},
        {"id": "p2", "text": "Original paragraph two."},
    ]
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_admin_revision_endpoints.py -v`
Expected: FAIL — tests fail because PUT still overwrites the story and response has no `revision` field

**Step 3: Modify admin.py — update response schemas**

In `app/routers/admin.py`, add the import at the top:

```python
from ..models.story_revision import StoryRevision
from ..schemas.story import RevisionResponse
```

Add a new response schema that includes the revision. Add after `AdminStoryListResponse`:

```python
class AdminRevisionInfo(BaseModel):
    id: str
    editor_id: str
    headline: str
    paragraphs: list[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminStoryWithRevisionResponse(BaseModel):
    id: str
    reporter_id: str
    headline: str
    category: Optional[str]
    location: Optional[str]
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reporter: AdminReporterInfo
    revision: Optional[AdminRevisionInfo] = None

    model_config = {"from_attributes": True}
```

**Step 4: Rewrite the PUT /admin/stories/{id} endpoint**

Replace the existing `admin_update_story` function:

```python
@router.put("/stories/{story_id}", response_model=AdminStoryWithRevisionResponse)
def admin_update_story(
    story_id: str,
    body: AdminStoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    story = (
        db.query(Story)
        .options(joinedload(Story.reporter), joinedload(Story.revision))
        .filter(Story.id == story_id)
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
        existing_rev.updated_at = datetime.now(timezone.utc)
    else:
        new_rev = StoryRevision(
            story_id=story.id,
            editor_id=current_user.id,
            headline=rev_headline,
            paragraphs=rev_paragraphs,
        )
        db.add(new_rev)

    # Update category on the story if provided (category is a story-level field, not content)
    if body.category is not None:
        story.category = body.category

    story.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(story)
    return story
```

**Important:** This endpoint now needs `get_current_user` to identify the editor. Add the import:

```python
from ..deps import get_current_user
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_admin_revision_endpoints.py -v`
Expected: 4 passed

**Step 6: Commit**

```bash
git add app/routers/admin.py tests/test_admin_revision_endpoints.py
git commit -m "feat: PUT /admin/stories/{id} upserts revision instead of overwriting story"
```

---

### Task 5: Modify GET /admin/stories/{id} to Include Revision

**Files:**
- Create: `tests/test_admin_get_revision.py`
- Modify: `app/routers/admin.py`

**Step 1: Write the failing tests**

Create `tests/test_admin_get_revision.py`:

```python
"""Tests for GET /admin/stories/{id} with revision data."""


def test_get_story_without_revision(client, auth_header, sample_story):
    resp = client.get(f"/admin/stories/{sample_story.id}", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["revision"] is None
    assert data["headline"] == "Original Headline"


def test_get_story_with_revision(client, auth_header, sample_story):
    # Create a revision via PUT
    client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Edited", "paragraphs": [{"id": "p1", "text": "new"}]},
        headers=auth_header,
    )

    resp = client.get(f"/admin/stories/{sample_story.id}", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["revision"] is not None
    assert data["revision"]["headline"] == "Edited"
    # Original preserved
    assert data["headline"] == "Original Headline"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_admin_get_revision.py -v`
Expected: FAIL — GET response does not include `revision` field

**Step 3: Update GET endpoint**

In `app/routers/admin.py`, change the GET endpoint's response model and add `joinedload(Story.revision)`:

```python
@router.get("/stories/{story_id}", response_model=AdminStoryWithRevisionResponse)
def admin_get_story(story_id: str, db: Session = Depends(get_db)):
    story = (
        db.query(Story)
        .options(joinedload(Story.reporter), joinedload(Story.revision))
        .filter(Story.id == story_id)
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )
    return story
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_admin_get_revision.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add app/routers/admin.py tests/test_admin_get_revision.py
git commit -m "feat: GET /admin/stories/{id} includes revision data"
```

---

### Task 6: Add has_revision Flag to GET /admin/stories List

**Files:**
- Create: `tests/test_admin_list_has_revision.py`
- Modify: `app/routers/admin.py`

**Step 1: Write the failing test**

Create `tests/test_admin_list_has_revision.py`:

```python
"""Tests for has_revision flag in story list."""


def test_list_stories_has_revision_flag(client, auth_header, sample_story, db):
    from app.models.story import Story

    # Create a second story (no revision)
    story2 = Story(
        id="story-2",
        reporter_id=sample_story.reporter_id,
        headline="Second Story",
        paragraphs=[],
        status="submitted",
    )
    db.add(story2)
    db.commit()

    # Create revision on first story
    client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Edited", "paragraphs": []},
        headers=auth_header,
    )

    resp = client.get("/admin/stories", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()

    stories_by_id = {s["id"]: s for s in data["stories"]}
    assert stories_by_id[sample_story.id]["has_revision"] is True
    assert stories_by_id["story-2"]["has_revision"] is False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_admin_list_has_revision.py -v`
Expected: FAIL — `has_revision` not in response

**Step 3: Add has_revision to the list response schema and endpoint**

In `app/routers/admin.py`, add a new response model for list items:

```python
class AdminStoryListItem(BaseModel):
    id: str
    reporter_id: str
    headline: str
    category: Optional[str]
    location: Optional[str]
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reporter: AdminReporterInfo
    has_revision: bool = False

    model_config = {"from_attributes": True}
```

Update `AdminStoryListResponse`:

```python
class AdminStoryListResponse(BaseModel):
    stories: list[AdminStoryListItem]
    total: int
```

Update the `admin_list_stories` endpoint to eagerly load revisions and add the flag:

```python
@router.get("/stories", response_model=AdminStoryListResponse)
def admin_list_stories(
    db: Session = Depends(get_db),
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

    # Add has_revision flag
    result = []
    for s in stories:
        item = AdminStoryListItem.model_validate(s)
        item.has_revision = s.revision is not None
        result.append(item)

    return AdminStoryListResponse(stories=result, total=total)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_admin_list_has_revision.py -v`
Expected: 1 passed

**Step 5: Run ALL tests to verify nothing is broken**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add app/routers/admin.py tests/test_admin_list_has_revision.py
git commit -m "feat: add has_revision flag to story list endpoint"
```

---

### Task 7: Update Frontend API Layer

**Files:**
- Modify: `reviewer-panel/src/services/api.js`

**Step 1: Update transformStory to handle revision data**

In the `transformStory` function in `api.js`, add revision handling. After the existing `return` block, update it to include `revision`:

```javascript
export function transformStory(story) {
  if (!story) return null;

  // ... existing code unchanged ...

  return {
    ...story,
    paragraphs,
    bodyText,
    reporter: reporterWithUI,
    reporterId: reporter.id || story.reporter_id,
    submittedAt: story.submitted_at || story.submittedAt,
    createdAt: story.created_at || story.createdAt,
    updatedAt: story.updated_at || story.updatedAt,
    location: story.location || reporter.area_name || '',
    mediaFiles,
    // Revision data (editor's version)
    revision: story.revision || null,
    hasRevision: story.has_revision ?? story.revision != null,
    // Fallback fields the UI expects
    priority: story.priority || 'normal',
    wordCount: bodyText ? bodyText.trim().split(/\s+/).length : 0,
    aiAccuracy: story.ai_accuracy || story.aiAccuracy || '0',
  };
}
```

**Step 2: Verify the dev server still starts without errors**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build 2>&1 | tail -5`
Expected: Build succeeds (or at least no import errors)

**Step 3: Commit**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
git add src/services/api.js
git commit -m "feat: add revision and hasRevision to transformStory"
```

---

### Task 8: Update ReviewPage to Load and Save Revisions

**Files:**
- Modify: `reviewer-panel/src/pages/ReviewPage.jsx`

**Step 1: Update story load to use revision content when present**

In the `useEffect` that fetches the story (around line 163), update the content loading logic:

```javascript
fetchStory(id)
  .then((data) => {
    if (!cancelled) {
      const transformed = transformStory(data);
      setStory(transformed);
      setStatus(transformed?.status || 'submitted');

      // Use revision content if it exists, otherwise original
      const rev = transformed?.revision;
      const activeHeadline = rev ? rev.headline : (transformed?.headline || '');
      const activeParagraphs = rev ? rev.paragraphs : (transformed?.paragraphs || []);

      setHeadline(activeHeadline);

      // Set editor content from active paragraphs
      if (editor && activeParagraphs.length > 0) {
        const html = activeParagraphs
          .map((p) => `<p>${(p.text || '').replace(/\n/g, '<br>')}</p>`)
          .join('');
        editor.commands.setContent(html);
      }
      setLoading(false);
    }
  })
```

**Step 2: handleSaveContent remains unchanged**

The `handleSaveContent` function already calls `updateStory(id, { headline, paragraphs })`, and the backend now upserts into `story_revisions`. No frontend save changes needed.

**Step 3: Verify the page loads correctly**

Start the dev server and navigate to a story. If a revision exists, the editor should show the revision content. If not, it shows the original.

**Step 4: Commit**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
git add src/pages/ReviewPage.jsx
git commit -m "feat: ReviewPage loads revision content when present"
```

---

### Task 9: Show Original Content in Properties Panel (Read-Only)

The properties panel on the right side of ReviewPage should always show the reporter's original content, regardless of whether a revision exists.

**Files:**
- Modify: `reviewer-panel/src/pages/ReviewPage.jsx`

**Step 1: Identify the properties panel section**

Search for the properties panel in ReviewPage.jsx. It shows story metadata (reporter, status, etc.). Add a read-only "Original Content" section that displays `story.headline` and `story.bodyText` (the original, not the revision).

**Step 2: Add original content display**

In the properties panel section (right sidebar), add after the existing metadata:

```jsx
{story.revision && (
  <div className={styles.originalContentSection}>
    <h4>Original Submission</h4>
    <p className={styles.originalHeadline}>{story.headline}</p>
    <div className={styles.originalBody}>
      {story.paragraphs?.map((p, i) => (
        <p key={i}>{p.text}</p>
      ))}
    </div>
  </div>
)}
```

**Step 3: Add CSS for the original content section**

In `ReviewPage.module.css`:

```css
.originalContentSection {
  margin-top: 1rem;
  padding: 0.75rem;
  background: var(--surface-secondary, #f5f5f5);
  border-radius: 8px;
  border-left: 3px solid var(--accent, #FA6C38);
}

.originalContentSection h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary, #666);
}

.originalHeadline {
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  font-size: 0.875rem;
}

.originalBody {
  font-size: 0.8125rem;
  color: var(--text-secondary, #555);
  line-height: 1.5;
  max-height: 200px;
  overflow-y: auto;
}

.originalBody p {
  margin: 0 0 0.5rem 0;
}
```

**Step 4: Verify visually**

Start the dev server, navigate to a story with a revision. The original content should appear in the sidebar panel.

**Step 5: Commit**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
git add src/pages/ReviewPage.jsx src/pages/ReviewPage.module.css
git commit -m "feat: show original submission in properties panel when revision exists"
```

---

### Task 10: Show "Edited" Badge in Stories List

**Files:**
- Modify: `reviewer-panel/src/pages/StoriesPage.jsx` (or wherever the story list is rendered)

**Step 1: Find the stories list component**

Search for the component that renders the list of stories. Add an "Edited" badge next to stories that have `has_revision: true`.

**Step 2: Add the badge**

In the story list item rendering, add:

```jsx
{story.hasRevision && (
  <span className={styles.editedBadge}>Edited</span>
)}
```

**Step 3: Add CSS for the badge**

```css
.editedBadge {
  display: inline-block;
  padding: 2px 6px;
  font-size: 0.625rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  background: #E8F5E9;
  color: #2E7D32;
  border-radius: 4px;
  margin-left: 0.5rem;
}
```

**Step 4: Verify visually**

Check the stories list — stories with revisions should show the "Edited" badge.

**Step 5: Commit**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
git add src/pages/StoriesPage.jsx src/pages/StoriesPage.module.css
git commit -m "feat: show Edited badge on stories with revisions in list view"
```

---

### Task 11: Final Integration Test and Cleanup

**Files:**
- Run all backend tests
- Manual end-to-end verification

**Step 1: Run all backend tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/ -v`
Expected: All tests pass

**Step 2: Start the API server and test manually**

Run: `cd /Users/admin/Desktop/newsflow-api && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

Verify:
1. Open a story in the reviewer panel
2. Edit the headline and content
3. Click Save Draft
4. Refresh the page — edited content should persist
5. Check the properties panel — original content should be shown
6. Check the stories list — "Edited" badge should appear
7. Check the API response: `GET /admin/stories/{id}` should show both original and revision

**Step 3: Final commit**

```bash
git commit -m "feat: story revisions — complete implementation"
```
