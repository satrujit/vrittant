"""GET /auth/me must include the org's active category keys.

The mobile create-news picker reads `reporter.org.categories` from this
endpoint and constrains the picker to those keys (falling back to a hardcoded
list when empty). Without this enrichment, mobile always sees an empty list
and falls back to the stale hardcoded categories — which means admins editing
the master category list in the panel has zero effect on mobile.

This test locks in: /auth/me returns active category keys from
org_configs.categories, in order, dropping inactive entries.
"""

from jose import jwt

from app.config import settings
from app.models.org_config import OrgConfig
from app.models.organization import Organization
from app.models.user import User


def _token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _setup_org(db, *, org_id: str = "org-cat-test", categories=None) -> Organization:
    org = Organization(id=org_id, name=f"Org {org_id}", slug=org_id)
    db.add(org)
    cfg = OrgConfig(
        organization_id=org_id,
        categories=categories or [],
        publication_types=[],
        page_suggestions=[],
        priority_levels=[],
        edition_schedule=[],
    )
    db.add(cfg)
    db.commit()
    return org


def _setup_reporter(db, *, org_id: str) -> User:
    user = User(
        id=f"reporter-{org_id}",
        name="Cat Reporter",
        phone=f"+9133{org_id[-7:].zfill(7)}",
        user_type="reporter",
        area_name="Test",
        organization=f"Org {org_id}",
        organization_id=org_id,
    )
    db.add(user)
    db.commit()
    return user


def test_me_returns_active_category_keys(client, db):
    _setup_org(
        db,
        org_id="org-cat-1",
        categories=[
            {"key": "politics", "label": "Politics", "is_active": True},
            {"key": "crime", "label": "Crime", "is_active": True},
            {"key": "sports", "label": "Sports", "is_active": True},
        ],
    )
    user = _setup_reporter(db, org_id="org-cat-1")

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {_token(user.id)}"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["org"] is not None
    assert body["org"]["categories"] == ["politics", "crime", "sports"]


def test_me_omits_inactive_categories(client, db):
    _setup_org(
        db,
        org_id="org-cat-2",
        categories=[
            {"key": "politics", "label": "Politics", "is_active": True},
            {"key": "business", "label": "Business", "is_active": False},
            {"key": "sports", "label": "Sports", "is_active": True},
        ],
    )
    user = _setup_reporter(db, org_id="org-cat-2")

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {_token(user.id)}"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["org"]["categories"] == ["politics", "sports"]


def test_me_returns_empty_list_when_org_has_no_config(client, db):
    # Org row exists but no OrgConfig — mobile falls back to hardcoded list.
    org = Organization(id="org-cat-3", name="Org 3", slug="org-cat-3")
    db.add(org)
    db.commit()
    user = _setup_reporter(db, org_id="org-cat-3")

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {_token(user.id)}"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["org"]["categories"] == []
