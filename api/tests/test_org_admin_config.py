from app.models.organization import Organization
from app.models.org_config import (
    OrgConfig, DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
    DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
)
from jose import jwt
from app.config import settings


def _make_org_with_config(db):
    org = Organization(id="org-test", name="Test Org", slug="test-org")
    db.add(org)
    db.flush()
    config = OrgConfig(
        organization_id="org-test", categories=DEFAULT_CATEGORIES,
        publication_types=DEFAULT_PUBLICATION_TYPES,
        page_suggestions=DEFAULT_PAGE_SUGGESTIONS,
        priority_levels=DEFAULT_PRIORITY_LEVELS, default_language="odia",
    )
    db.add(config)
    db.commit()
    return org


class TestGetConfig:
    def test_org_admin_can_get_config(self, client, db, org_admin, org_admin_header):
        _make_org_with_config(db)
        resp = client.get("/admin/config", headers=org_admin_header)
        assert resp.status_code == 200
        assert len(resp.json()["categories"]) == 8
        assert resp.json()["default_language"] == "odia"

    def test_reviewer_cannot_get_admin_config(self, client, db, reviewer, auth_header):
        _make_org_with_config(db)
        resp = client.get("/admin/config", headers=auth_header)
        assert resp.status_code == 403


class TestUpdateConfig:
    def test_org_admin_can_update_categories(self, client, db, org_admin, org_admin_header):
        _make_org_with_config(db)
        resp = client.put("/admin/config", json={
            "categories": [
                {"key": "politics", "label": "Politics", "label_local": "\u0b30\u0b3e\u0b1c\u0b28\u0b40\u0b24\u0b3f", "is_active": True},
                {"key": "sports", "label": "Sports", "label_local": "\u0b15\u0b4d\u0b30\u0b40\u0b21\u0b3c\u0b3e", "is_active": False},
            ],
        }, headers=org_admin_header)
        assert resp.status_code == 200
        assert len(resp.json()["categories"]) == 2

    def test_partial_update_preserves_other_fields(self, client, db, org_admin, org_admin_header):
        _make_org_with_config(db)
        resp = client.put("/admin/config", json={"default_language": "english"}, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["default_language"] == "english"
        assert len(resp.json()["categories"]) == 8


class TestPublicConfig:
    def test_authenticated_user_can_get_config(self, client, db, reporter):
        _make_org_with_config(db)
        token = jwt.encode({"sub": reporter.id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        header = {"Authorization": f"Bearer {token}"}
        resp = client.get("/config/me", headers=header)
        assert resp.status_code == 200
        assert "categories" in resp.json()
