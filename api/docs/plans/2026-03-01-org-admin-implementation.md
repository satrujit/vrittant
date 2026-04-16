# Org Admin Role & Master Data Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `org_admin` role replacing `admin`, with user management, org settings, story deletion, and master data configuration.

**Architecture:** New `OrgConfig` model stores per-org master data as JSON columns. New `require_org_admin` dependency guards org-admin-only endpoints. Existing `require_reviewer` updated to accept `org_admin`. All new endpoints live in existing `admin.py` router.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, SQLite (dev), pytest

---

### Task 1: OrgConfig Model

**Files:**
- Create: `app/models/org_config.py`
- Modify: `app/main.py:9-10` (import to ensure table creation)

**Step 1: Create the OrgConfig model**

Create `app/models/org_config.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import relationship

from ..database import Base

DEFAULT_CATEGORIES = [
    {"key": "politics", "label": "Politics", "label_local": "ରାଜନୀତି", "is_active": True},
    {"key": "sports", "label": "Sports", "label_local": "କ୍ରୀଡ଼ା", "is_active": True},
    {"key": "crime", "label": "Crime", "label_local": "ଅପରାଧ", "is_active": True},
    {"key": "business", "label": "Business", "label_local": "ବ୍ୟବସାୟ", "is_active": True},
    {"key": "entertainment", "label": "Entertainment", "label_local": "ମନୋରଞ୍ଜନ", "is_active": True},
    {"key": "education", "label": "Education", "label_local": "ଶିକ୍ଷା", "is_active": True},
    {"key": "health", "label": "Health", "label_local": "ସ୍ୱାସ୍ଥ୍ୟ", "is_active": True},
    {"key": "technology", "label": "Technology", "label_local": "ପ୍ରଯୁକ୍ତି", "is_active": True},
]

DEFAULT_PUBLICATION_TYPES = [
    {"key": "daily", "label": "Daily", "is_active": True},
    {"key": "weekend", "label": "Weekend", "is_active": True},
    {"key": "evening", "label": "Evening", "is_active": True},
    {"key": "special", "label": "Special", "is_active": True},
]

DEFAULT_PAGE_SUGGESTIONS = [
    {"name": "Front Page", "sort_order": 1, "is_active": True},
    {"name": "Page 2", "sort_order": 2, "is_active": True},
    {"name": "Page 3", "sort_order": 3, "is_active": True},
    {"name": "Sports", "sort_order": 4, "is_active": True},
    {"name": "Entertainment", "sort_order": 5, "is_active": True},
    {"name": "State", "sort_order": 6, "is_active": True},
    {"name": "National", "sort_order": 7, "is_active": True},
    {"name": "International", "sort_order": 8, "is_active": True},
    {"name": "Editorial", "sort_order": 9, "is_active": True},
    {"name": "Classifieds", "sort_order": 10, "is_active": True},
]

DEFAULT_PRIORITY_LEVELS = [
    {"key": "normal", "label": "Normal", "label_local": "ସାଧାରଣ", "is_active": True},
    {"key": "urgent", "label": "Urgent", "label_local": "ଜରୁରୀ", "is_active": True},
    {"key": "breaking", "label": "Breaking", "label_local": "ବ୍ରେକିଂ", "is_active": True},
]


class OrgConfig(Base):
    __tablename__ = "org_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    categories = Column(JSON, nullable=False, default=list)
    publication_types = Column(JSON, nullable=False, default=list)
    page_suggestions = Column(JSON, nullable=False, default=list)
    priority_levels = Column(JSON, nullable=False, default=list)
    default_language = Column(String, nullable=False, default="odia")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    org = relationship("Organization")
```

**Step 2: Import in main.py so table gets created**

In `app/main.py`, after line 10 (`from .models.page_template import PageTemplate`), add:

```python
from .models.org_config import OrgConfig  # noqa: F401
```

**Step 3: Run server to verify table creation**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m uvicorn app.main:app --port 8000`
Expected: Server starts without errors, `org_configs` table created in SQLite.

**Step 4: Commit**

```bash
git add app/models/org_config.py app/main.py
git commit -m "feat: add OrgConfig model for per-org master data"
```

---

### Task 2: Rename admin → org_admin and add require_org_admin

**Files:**
- Modify: `app/deps.py:50-53` (update `require_reviewer`, add `require_org_admin`)
- Modify: `app/models/user.py:17` (update comment)
- Modify: `app/main.py` (update seed data user_types)

**Step 1: Update deps.py**

In `app/deps.py`, change the `require_reviewer` function to accept `org_admin` instead of `admin`:

```python
def require_reviewer(user: User = Depends(get_current_user)) -> User:
    """Require authenticated user with reviewer or org_admin role."""
    if user.user_type not in ("reviewer", "org_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer access required")
    return user
```

Add a new function after `require_reviewer`:

```python
def require_org_admin(user: User = Depends(get_current_user)) -> User:
    """Require authenticated user with org_admin role."""
    if user.user_type != "org_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Org admin access required")
    return user
```

**Step 2: Update user model comment**

In `app/models/user.py` line 17, change:

```python
    user_type = Column(String, nullable=False, default="reporter")  # reporter | reviewer | org_admin
```

**Step 3: Update seed data in main.py**

In `app/main.py`, the seed function currently does NOT create any `admin` users — all elevated users are `reviewer`. No changes needed to seed user_types.

However, add OrgConfig seeding. After the entitlement seeding for each org (after `db.commit()` at the end of the seed function, but before the `finally` block), add:

```python
        # ── Seed OrgConfig for each org ──
        from .models.org_config import (
            OrgConfig, DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
            DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
        )
        if db.query(OrgConfig).count() == 0:
            for org in orgs:
                db.add(OrgConfig(
                    organization_id=org.id,
                    categories=DEFAULT_CATEGORIES,
                    publication_types=DEFAULT_PUBLICATION_TYPES,
                    page_suggestions=DEFAULT_PAGE_SUGGESTIONS,
                    priority_levels=DEFAULT_PRIORITY_LEVELS,
                    default_language="odia",
                ))
            db.commit()
```

Also update one of the Pragativadi reviewers to be `org_admin` for testing. Change the `prag_reviewer1` creation (the "Editor Reviewer" user with phone `+918984336534`):

```python
            prag_reviewer1 = User(
                name="Editor Reviewer",
                phone="+918984336534",
                user_type="org_admin",
                organization="Pragativadi",
                organization_id="org-pragativadi",
            )
```

And similarly for Sambad and Prajaspoorthi — change their single reviewer to `org_admin`:

For Sambad's `sambad_reviewer`:
```python
            sambad_reviewer = User(
                name="Sambad Editor",
                phone="+919000000103",
                user_type="org_admin",
                organization="Sambad",
                organization_id="org-sambad",
            )
```

For Prajaspoorthi's `praja_reviewer`:
```python
            praja_reviewer = User(
                name="Prajaspoorthi Editor",
                phone="+919000000203",
                user_type="org_admin",
                organization="Prajaspoorthi",
                organization_id="org-prajaspoorthi",
            )
```

**Step 4: Update conftest.py for tests**

In `tests/conftest.py`, add an `org_admin` fixture after the `reporter` fixture:

```python
@pytest.fixture()
def org_admin(db):
    """Create and return an org_admin user."""
    user = User(
        id="org-admin-1",
        name="Test Org Admin",
        phone="+913333333333",
        user_type="org_admin",
        organization="Test Org",
        organization_id="org-test",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def org_admin_header(org_admin):
    """JWT Authorization header for the org_admin."""
    token = jwt.encode({"sub": org_admin.id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}
```

Also add `organization_id` to the existing `reviewer` and `reporter` fixtures (currently missing):

Update `reviewer` fixture:
```python
@pytest.fixture()
def reviewer(db):
    """Create and return a reviewer user."""
    user = User(
        id="reviewer-1",
        name="Test Reviewer",
        phone="+911111111111",
        user_type="reviewer",
        organization="Test Org",
        organization_id="org-test",
    )
    db.add(user)
    db.commit()
    return user
```

Update `reporter` fixture:
```python
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
        organization_id="org-test",
    )
    db.add(user)
    db.commit()
    return user
```

Update `sample_story` fixture to include `organization_id`:
```python
@pytest.fixture()
def sample_story(db, reporter):
    """Create and return a submitted story."""
    story = Story(
        id="story-1",
        reporter_id=reporter.id,
        organization_id="org-test",
        headline="Original Headline",
        category="politics",
        paragraphs=[{"id": "p1", "text": "Original paragraph one."}, {"id": "p2", "text": "Original paragraph two."}],
        status="submitted",
    )
    db.add(story)
    db.commit()
    return story
```

**Step 5: Run existing tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/ -v`
Expected: All existing tests pass (org_admin is accepted by `require_reviewer`).

**Step 6: Commit**

```bash
git add app/deps.py app/models/user.py app/main.py tests/conftest.py
git commit -m "feat: rename admin to org_admin, add require_org_admin dep"
```

---

### Task 3: Org Admin Schemas

**Files:**
- Create: `app/schemas/org_admin.py`

**Step 1: Create the schemas file**

Create `app/schemas/org_admin.py`:

```python
from typing import Optional
from pydantic import BaseModel, Field


# ── User management ──

class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=10, max_length=16, pattern=r'^\+\d{10,15}$')
    email: Optional[str] = None
    area_name: str = ""
    user_type: str = Field(default="reporter", pattern=r'^(reporter|reviewer)$')


class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = None
    area_name: Optional[str] = None
    is_active: Optional[bool] = None


class UpdateUserRoleRequest(BaseModel):
    user_type: str = Field(..., pattern=r'^(reporter|reviewer)$')


class UpdateUserEntitlementsRequest(BaseModel):
    page_keys: list[str]


class UserManagementResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    user_type: str
    area_name: str
    is_active: bool
    entitlements: list[str] = []

    model_config = {"from_attributes": True}


# ── Org management ──

class UpdateOrgRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    theme_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    logo_url: Optional[str] = None
    theme_color: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Master data config ──

class CategoryItem(BaseModel):
    key: str
    label: str
    label_local: str = ""
    is_active: bool = True


class PublicationTypeItem(BaseModel):
    key: str
    label: str
    is_active: bool = True


class PageSuggestionItem(BaseModel):
    name: str
    sort_order: int = 0
    is_active: bool = True


class PriorityLevelItem(BaseModel):
    key: str
    label: str
    label_local: str = ""
    is_active: bool = True


class UpdateOrgConfigRequest(BaseModel):
    categories: Optional[list[CategoryItem]] = None
    publication_types: Optional[list[PublicationTypeItem]] = None
    page_suggestions: Optional[list[PageSuggestionItem]] = None
    priority_levels: Optional[list[PriorityLevelItem]] = None
    default_language: Optional[str] = None


class OrgConfigResponse(BaseModel):
    categories: list[dict] = []
    publication_types: list[dict] = []
    page_suggestions: list[dict] = []
    priority_levels: list[dict] = []
    default_language: str = "odia"

    model_config = {"from_attributes": True}
```

**Step 2: Commit**

```bash
git add app/schemas/org_admin.py
git commit -m "feat: add Pydantic schemas for org admin endpoints"
```

---

### Task 4: User Management Endpoints

**Files:**
- Modify: `app/routers/admin.py` (add user management endpoints)
- Create: `tests/test_org_admin_users.py`

**Step 1: Write tests for user management**

Create `tests/test_org_admin_users.py`:

```python
import pytest
from jose import jwt
from app.config import settings
from app.models.user import User, Entitlement


class TestCreateUser:
    def test_org_admin_can_create_user(self, client, db, org_admin, org_admin_header):
        resp = client.post("/admin/users", json={
            "name": "New Reporter",
            "phone": "+914444444444",
            "area_name": "Delhi",
            "user_type": "reporter",
        }, headers=org_admin_header)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Reporter"
        assert data["phone"] == "+914444444444"
        assert data["user_type"] == "reporter"

    def test_reviewer_cannot_create_user(self, client, db, reviewer, auth_header):
        resp = client.post("/admin/users", json={
            "name": "New Reporter",
            "phone": "+914444444444",
            "user_type": "reporter",
        }, headers=auth_header)
        assert resp.status_code == 403

    def test_cannot_create_org_admin(self, client, db, org_admin, org_admin_header):
        resp = client.post("/admin/users", json={
            "name": "Another Admin",
            "phone": "+914444444444",
            "user_type": "org_admin",
        }, headers=org_admin_header)
        assert resp.status_code == 422  # validation rejects org_admin

    def test_duplicate_phone_rejected(self, client, db, org_admin, org_admin_header):
        client.post("/admin/users", json={
            "name": "First",
            "phone": "+914444444444",
            "user_type": "reporter",
        }, headers=org_admin_header)
        resp = client.post("/admin/users", json={
            "name": "Second",
            "phone": "+914444444444",
            "user_type": "reporter",
        }, headers=org_admin_header)
        assert resp.status_code == 409


class TestUpdateUser:
    def test_org_admin_can_disable_user(self, client, db, org_admin, org_admin_header, reporter):
        resp = client.put(f"/admin/users/{reporter.id}", json={
            "is_active": False,
        }, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_cannot_update_user_from_other_org(self, client, db, org_admin, org_admin_header):
        other_user = User(
            id="other-org-user",
            name="Other",
            phone="+915555555555",
            user_type="reporter",
            organization="Other Org",
            organization_id="org-other",
        )
        db.add(other_user)
        db.commit()
        resp = client.put(f"/admin/users/{other_user.id}", json={
            "is_active": False,
        }, headers=org_admin_header)
        assert resp.status_code == 404


class TestUpdateUserRole:
    def test_org_admin_can_change_role(self, client, db, org_admin, org_admin_header, reporter):
        resp = client.put(f"/admin/users/{reporter.id}/role", json={
            "user_type": "reviewer",
        }, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["user_type"] == "reviewer"

    def test_cannot_assign_org_admin_role(self, client, db, org_admin, org_admin_header, reporter):
        resp = client.put(f"/admin/users/{reporter.id}/role", json={
            "user_type": "org_admin",
        }, headers=org_admin_header)
        assert resp.status_code == 422


class TestUpdateUserEntitlements:
    def test_org_admin_can_set_entitlements(self, client, db, org_admin, org_admin_header, reporter):
        resp = client.put(f"/admin/users/{reporter.id}/entitlements", json={
            "page_keys": ["dashboard", "stories"],
        }, headers=org_admin_header)
        assert resp.status_code == 200
        assert sorted(resp.json()["entitlements"]) == ["dashboard", "stories"]

    def test_replaces_existing_entitlements(self, client, db, org_admin, org_admin_header, reporter):
        # Set initial
        client.put(f"/admin/users/{reporter.id}/entitlements", json={
            "page_keys": ["dashboard", "stories", "review"],
        }, headers=org_admin_header)
        # Replace
        resp = client.put(f"/admin/users/{reporter.id}/entitlements", json={
            "page_keys": ["dashboard"],
        }, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["entitlements"] == ["dashboard"]
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_org_admin_users.py -v`
Expected: FAIL — endpoints don't exist yet.

**Step 3: Add user management endpoints to admin.py**

In `app/routers/admin.py`, add these imports at the top (after existing imports):

```python
from ..deps import get_current_user, require_reviewer, get_current_org_id, require_org_admin
from ..models.user import User, Entitlement
from ..schemas.org_admin import (
    CreateUserRequest, UpdateUserRequest, UpdateUserRoleRequest,
    UpdateUserEntitlementsRequest, UserManagementResponse,
)
```

Remove the duplicate `User` import from the existing line:
```python
from ..models.user import User
```
(It's now imported above.)

Add these endpoints at the bottom of `admin.py`:

```python
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
        name=body.name,
        phone=body.phone,
        email=body.email,
        area_name=body.area_name,
        user_type=body.user_type,
        organization=org.name if org else "",
        organization_id=org_id,
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
    user_id: str,
    body: UpdateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.name is not None:
        user.name = body.name
    if body.email is not None:
        user.email = body.email
    if body.area_name is not None:
        user.area_name = body.area_name
    if body.is_active is not None:
        user.is_active = body.is_active

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
    user_id: str,
    body: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
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
    user_id: str,
    body: UpdateUserEntitlementsRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Delete existing entitlements and replace
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
```

Also add the Organization import at the top of `admin.py`:

```python
from ..models.organization import Organization
```

**Step 4: Run tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_org_admin_users.py -v`
Expected: All tests pass.

**Step 5: Commit**

```bash
git add app/routers/admin.py app/schemas/org_admin.py tests/test_org_admin_users.py
git commit -m "feat: add user management endpoints for org_admin"
```

---

### Task 5: Org Management Endpoints

**Files:**
- Modify: `app/routers/admin.py` (add org update + logo upload)
- Create: `tests/test_org_admin_org.py`

**Step 1: Write tests**

Create `tests/test_org_admin_org.py`:

```python
import pytest
from app.models.organization import Organization


@pytest.fixture()
def test_org(db):
    org = Organization(
        id="org-test",
        name="Test Org",
        slug="test-org",
        theme_color="#FF0000",
    )
    db.add(org)
    db.commit()
    return org


class TestUpdateOrg:
    def test_org_admin_can_update_org(self, client, db, test_org, org_admin, org_admin_header):
        resp = client.put("/admin/org", json={
            "name": "Updated Org",
            "theme_color": "#00FF00",
        }, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Org"
        assert resp.json()["theme_color"] == "#00FF00"

    def test_reviewer_cannot_update_org(self, client, db, test_org, reviewer, auth_header):
        resp = client.put("/admin/org", json={
            "name": "Hacked",
        }, headers=auth_header)
        assert resp.status_code == 403

    def test_partial_update(self, client, db, test_org, org_admin, org_admin_header):
        resp = client.put("/admin/org", json={
            "theme_color": "#0000FF",
        }, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Org"  # unchanged
        assert resp.json()["theme_color"] == "#0000FF"


class TestUploadLogo:
    def test_org_admin_can_upload_logo(self, client, db, test_org, org_admin, org_admin_header):
        # Create a tiny PNG (1x1 pixel)
        import struct, zlib
        def make_png():
            sig = b'\x89PNG\r\n\x1a\n'
            ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
            ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
            ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
            raw = zlib.compress(b'\x00\x00\x00\x00')
            idat_crc = zlib.crc32(b'IDAT' + raw) & 0xffffffff
            idat = struct.pack('>I', len(raw)) + b'IDAT' + raw + struct.pack('>I', idat_crc)
            iend_crc = zlib.crc32(b'IEND') & 0xffffffff
            iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
            return sig + ihdr + idat + iend
        png_bytes = make_png()
        resp = client.put(
            "/admin/org/logo",
            files={"file": ("logo.png", png_bytes, "image/png")},
            headers=org_admin_header,
        )
        assert resp.status_code == 200
        assert "/uploads/org-logos/" in resp.json()["logo_url"]
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_org_admin_org.py -v`
Expected: FAIL.

**Step 3: Add org management endpoints to admin.py**

Add these imports at the top of `admin.py` (if not already present):

```python
from ..schemas.org_admin import UpdateOrgRequest, OrgResponse
```

Add to the imports at top:
```python
import os
import uuid as uuid_mod
from fastapi import UploadFile, File as FastAPIFile
```

Add endpoints at the bottom of `admin.py`:

```python
# ---------------------------------------------------------------------------
# PUT /admin/org  (org_admin only)
# ---------------------------------------------------------------------------

@router.put("/org", response_model=OrgResponse)
def update_org(
    body: UpdateOrgRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if body.name is not None:
        org.name = body.name
    if body.theme_color is not None:
        org.theme_color = body.theme_color

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
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
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
```

**Step 4: Run tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_org_admin_org.py -v`
Expected: All tests pass.

**Step 5: Commit**

```bash
git add app/routers/admin.py tests/test_org_admin_org.py
git commit -m "feat: add org management endpoints (update details + logo)"
```

---

### Task 6: Master Data Config Endpoints

**Files:**
- Modify: `app/routers/admin.py` (add config endpoints)
- Create: `tests/test_org_admin_config.py`

**Step 1: Write tests**

Create `tests/test_org_admin_config.py`:

```python
import pytest
from app.models.organization import Organization
from app.models.org_config import (
    OrgConfig, DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
    DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
)


@pytest.fixture()
def test_org_with_config(db):
    org = Organization(id="org-test", name="Test Org", slug="test-org")
    db.add(org)
    db.flush()
    config = OrgConfig(
        organization_id="org-test",
        categories=DEFAULT_CATEGORIES,
        publication_types=DEFAULT_PUBLICATION_TYPES,
        page_suggestions=DEFAULT_PAGE_SUGGESTIONS,
        priority_levels=DEFAULT_PRIORITY_LEVELS,
        default_language="odia",
    )
    db.add(config)
    db.commit()
    return org


class TestGetConfig:
    def test_org_admin_can_get_config(self, client, db, test_org_with_config, org_admin, org_admin_header):
        resp = client.get("/admin/config", headers=org_admin_header)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["categories"]) == 8
        assert data["default_language"] == "odia"

    def test_reviewer_cannot_get_admin_config(self, client, db, test_org_with_config, reviewer, auth_header):
        resp = client.get("/admin/config", headers=auth_header)
        assert resp.status_code == 403


class TestUpdateConfig:
    def test_org_admin_can_update_categories(self, client, db, test_org_with_config, org_admin, org_admin_header):
        resp = client.put("/admin/config", json={
            "categories": [
                {"key": "politics", "label": "Politics", "label_local": "ରାଜନୀତି", "is_active": True},
                {"key": "sports", "label": "Sports", "label_local": "କ୍ରୀଡ଼ା", "is_active": False},
            ],
        }, headers=org_admin_header)
        assert resp.status_code == 200
        assert len(resp.json()["categories"]) == 2

    def test_partial_update_preserves_other_fields(self, client, db, test_org_with_config, org_admin, org_admin_header):
        resp = client.put("/admin/config", json={
            "default_language": "english",
        }, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["default_language"] == "english"
        assert len(resp.json()["categories"]) == 8  # unchanged


class TestPublicConfig:
    def test_authenticated_user_can_get_config(self, client, db, test_org_with_config, reporter, auth_header):
        # Reporter uses reviewer's auth_header from conftest — need reporter header
        from jose import jwt
        from app.config import settings
        token = jwt.encode({"sub": reporter.id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        header = {"Authorization": f"Bearer {token}"}
        resp = client.get("/config/me", headers=header)
        assert resp.status_code == 200
        assert "categories" in resp.json()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_org_admin_config.py -v`
Expected: FAIL.

**Step 3: Add config endpoints to admin.py**

Add imports:

```python
from ..models.org_config import OrgConfig
from ..schemas.org_admin import UpdateOrgConfigRequest, OrgConfigResponse
```

Add endpoints to `admin.py`:

```python
# ---------------------------------------------------------------------------
# GET /admin/config  (org_admin only)
# ---------------------------------------------------------------------------

@router.get("/config", response_model=OrgConfigResponse)
def get_org_config(
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
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
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
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
```

**Step 4: Add the public config endpoint**

This needs a separate router since it's not under `/admin`. Create the endpoint in `app/routers/admin.py` but using a separate prefix — OR add it to a new lightweight router.

The simplest approach: add it to `admin.py` but register a second router. Instead, add it directly to `app/main.py` as a simple function, or add to auth.py. Simplest: add to the existing admin router file but with a separate router.

Add at the top of `admin.py`, after the existing `router` definition:

```python
config_router = APIRouter(prefix="/config", tags=["config"])
```

Add the endpoint:

```python
# ---------------------------------------------------------------------------
# GET /config/me  (any authenticated user)
# ---------------------------------------------------------------------------

@config_router.get("/me", response_model=OrgConfigResponse)
def get_my_org_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
):
    config = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return config
```

Then in `app/main.py`, register the new router. After the line `app.include_router(admin.router)`, add:

```python
app.include_router(admin.config_router)
```

**Step 5: Run tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_org_admin_config.py -v`
Expected: All tests pass.

**Step 6: Run all tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/ -v`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add app/routers/admin.py app/main.py tests/test_org_admin_config.py
git commit -m "feat: add master data config endpoints (get/update + public /config/me)"
```

---

### Task 7: Story Deletion Endpoint

**Files:**
- Modify: `app/routers/admin.py` (add DELETE endpoint)
- Create: `tests/test_org_admin_delete_story.py`

**Step 1: Write tests**

Create `tests/test_org_admin_delete_story.py`:

```python
import pytest
from app.models.story import Story
from app.models.organization import Organization


@pytest.fixture()
def test_org(db):
    org = Organization(id="org-test", name="Test Org", slug="test-org")
    db.add(org)
    db.commit()
    return org


@pytest.fixture()
def published_story(db, reporter, test_org):
    story = Story(
        id="story-published",
        reporter_id=reporter.id,
        organization_id="org-test",
        headline="Published Story",
        category="politics",
        paragraphs=[],
        status="published",
    )
    db.add(story)
    db.commit()
    return story


class TestDeleteStory:
    def test_org_admin_can_delete_any_story(self, client, db, test_org, org_admin, org_admin_header, published_story):
        resp = client.delete(f"/admin/stories/{published_story.id}", headers=org_admin_header)
        assert resp.status_code == 204
        assert db.query(Story).filter(Story.id == published_story.id).first() is None

    def test_reviewer_cannot_delete_story(self, client, db, test_org, reviewer, auth_header, published_story):
        resp = client.delete(f"/admin/stories/{published_story.id}", headers=auth_header)
        assert resp.status_code == 403

    def test_delete_nonexistent_story(self, client, db, test_org, org_admin, org_admin_header):
        resp = client.delete("/admin/stories/nonexistent", headers=org_admin_header)
        assert resp.status_code == 404

    def test_cannot_delete_story_from_other_org(self, client, db, test_org, org_admin, org_admin_header, reporter):
        story = Story(
            id="story-other-org",
            reporter_id=reporter.id,
            organization_id="org-other",
            headline="Other Org Story",
            paragraphs=[],
            status="published",
        )
        db.add(story)
        db.commit()
        resp = client.delete(f"/admin/stories/{story.id}", headers=org_admin_header)
        assert resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_org_admin_delete_story.py -v`
Expected: FAIL.

**Step 3: Add delete endpoint to admin.py**

Add endpoint:

```python
# ---------------------------------------------------------------------------
# DELETE /admin/stories/{story_id}  (org_admin only)
# ---------------------------------------------------------------------------

@router.delete("/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_story(
    story_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    # Delete associated revision if exists
    if story.revision:
        db.delete(story.revision)
    db.delete(story)
    db.commit()
```

**Important:** This DELETE endpoint must be placed BEFORE the existing `GET /stories/{story_id}` and `PUT /stories/{story_id}` endpoints in the file, because FastAPI matches routes in order and the existing `PUT /stories/{story_id}/status` endpoint uses `require_reviewer`. Actually, since the method is DELETE (not GET/PUT), there's no conflict — just add it at the bottom.

**Step 4: Run tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/test_org_admin_delete_story.py -v`
Expected: All tests pass.

**Step 5: Run full test suite**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/ -v`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add app/routers/admin.py tests/test_org_admin_delete_story.py
git commit -m "feat: add story deletion endpoint for org_admin"
```

---

### Task 8: Reset Dev Database and Smoke Test

**Step 1: Delete existing SQLite DB to trigger fresh seed**

Run: `rm -f /Users/admin/Desktop/newsflow-api/newsflow.db`

**Step 2: Start the server**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`

Expected: Server starts, tables created, seed data includes org_configs for all 3 orgs and one org_admin per org.

**Step 3: Smoke test with curl**

Test login as org_admin (Editor Reviewer, +918984336534):
```bash
curl -s http://localhost:8000/auth/verify-otp -H 'Content-Type: application/json' -d '{"phone": "+918984336534", "otp": "1234"}' | python3 -m json.tool
```

Then use the returned token to test:

```bash
TOKEN=<token from above>

# Get config
curl -s http://localhost:8000/admin/config -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Get public config
curl -s http://localhost:8000/config/me -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# List users (existing reporters endpoint should still work)
curl -s http://localhost:8000/admin/reporters -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Step 4: Commit (no code changes, just verification)**

No commit needed — this was a verification step.

---

### Task 9: Run Full Test Suite and Final Commit

**Step 1: Run all tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m pytest tests/ -v`
Expected: All tests pass.

**Step 2: Final verification commit if any fixups were needed**

```bash
git add -A && git commit -m "test: ensure all org admin tests pass"
```
