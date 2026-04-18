"""Task 9: admin user CRUD manages reviewer beats (categories/regions) and requires reporter area."""
from app.models.org_config import OrgConfig
from app.models.user import User


def _seed_org_config(db, org_id="org-test"):
    cfg = OrgConfig(
        organization_id=org_id,
        categories=[
            {"key": "politics", "label": "Politics", "is_active": True},
            {"key": "sports", "label": "Sports", "is_active": True},
            {"key": "local", "label": "Local", "is_active": True},
        ],
        publication_types=[],
        page_suggestions=[],
        priority_levels=[],
    )
    db.add(cfg)
    db.commit()
    return cfg


def test_create_reviewer_with_beats(client, db, org_admin, org_admin_header):
    _seed_org_config(db)
    resp = client.post(
        "/admin/users",
        json={
            "name": "Beat Reviewer",
            "phone": "+916666666666",
            "user_type": "reviewer",
            "categories": ["politics"],
            "regions": ["Cuttack"],
        },
        headers=org_admin_header,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["categories"] == ["politics"]
    assert data["regions"] == ["Cuttack"]

    db.expire_all()
    user = db.query(User).filter(User.id == data["id"]).first()
    assert user.categories == ["politics"]
    assert user.regions == ["Cuttack"]


def test_update_reviewer_categories(client, db, org_admin, org_admin_header, reviewer):
    _seed_org_config(db)
    resp = client.put(
        f"/admin/users/{reviewer.id}",
        json={"categories": ["sports", "local"], "regions": ["Bhubaneswar"]},
        headers=org_admin_header,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["categories"] == ["sports", "local"]
    assert body["regions"] == ["Bhubaneswar"]

    db.expire_all()
    user = db.query(User).filter(User.id == reviewer.id).first()
    assert user.categories == ["sports", "local"]
    assert user.regions == ["Bhubaneswar"]


def test_create_reporter_without_area_name_fails(client, db, org_admin, org_admin_header):
    _seed_org_config(db)
    resp = client.post(
        "/admin/users",
        json={
            "name": "No Area Reporter",
            "phone": "+917777777777",
            "user_type": "reporter",
        },
        headers=org_admin_header,
    )
    assert resp.status_code == 422, resp.text


def test_create_reviewer_unknown_category_400(client, db, org_admin, org_admin_header):
    _seed_org_config(db)
    resp = client.post(
        "/admin/users",
        json={
            "name": "Bad Beat",
            "phone": "+918888888888",
            "user_type": "reviewer",
            "categories": ["weather"],
        },
        headers=org_admin_header,
    )
    assert resp.status_code == 400, resp.text
    assert "Unknown category" in resp.json()["detail"]
