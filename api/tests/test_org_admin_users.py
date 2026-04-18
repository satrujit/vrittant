from app.models.user import User, Entitlement


class TestCreateUser:
    def test_org_admin_can_create_user(self, client, db, org_admin, org_admin_header):
        resp = client.post("/admin/users", json={
            "name": "New Reporter", "phone": "+914444444444",
            "area_name": "Delhi", "user_type": "reporter",
        }, headers=org_admin_header)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Reporter"
        assert data["phone"] == "+914444444444"
        assert data["user_type"] == "reporter"

    def test_reviewer_cannot_create_user(self, client, db, reviewer, auth_header):
        resp = client.post("/admin/users", json={
            "name": "New Reporter", "phone": "+914444444444", "user_type": "reporter",
        }, headers=auth_header)
        assert resp.status_code == 403

    def test_cannot_create_org_admin(self, client, db, org_admin, org_admin_header):
        resp = client.post("/admin/users", json={
            "name": "Another Admin", "phone": "+914444444444", "user_type": "org_admin",
        }, headers=org_admin_header)
        assert resp.status_code == 422

    def test_duplicate_phone_rejected(self, client, db, org_admin, org_admin_header):
        client.post("/admin/users", json={
            "name": "First", "phone": "+914444444444", "area_name": "Delhi", "user_type": "reporter",
        }, headers=org_admin_header)
        resp = client.post("/admin/users", json={
            "name": "Second", "phone": "+914444444444", "area_name": "Delhi", "user_type": "reporter",
        }, headers=org_admin_header)
        assert resp.status_code == 409


class TestUpdateUser:
    def test_org_admin_can_disable_user(self, client, db, org_admin, org_admin_header, reporter):
        resp = client.put(f"/admin/users/{reporter.id}", json={"is_active": False}, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_cannot_update_user_from_other_org(self, client, db, org_admin, org_admin_header):
        other = User(id="other-org-user", name="Other", phone="+915555555555",
                     user_type="reporter", organization="Other", organization_id="org-other")
        db.add(other)
        db.commit()
        resp = client.put(f"/admin/users/{other.id}", json={"is_active": False}, headers=org_admin_header)
        assert resp.status_code == 404


class TestUpdateUserRole:
    def test_org_admin_can_change_role(self, client, db, org_admin, org_admin_header, reporter):
        resp = client.put(f"/admin/users/{reporter.id}/role", json={"user_type": "reviewer"}, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["user_type"] == "reviewer"

    def test_cannot_assign_org_admin_role(self, client, db, org_admin, org_admin_header, reporter):
        resp = client.put(f"/admin/users/{reporter.id}/role", json={"user_type": "org_admin"}, headers=org_admin_header)
        assert resp.status_code == 422


class TestUpdateUserEntitlements:
    def test_org_admin_can_set_entitlements(self, client, db, org_admin, org_admin_header, reporter):
        resp = client.put(f"/admin/users/{reporter.id}/entitlements",
                          json={"page_keys": ["dashboard", "stories"]}, headers=org_admin_header)
        assert resp.status_code == 200
        assert sorted(resp.json()["entitlements"]) == ["dashboard", "stories"]

    def test_replaces_existing_entitlements(self, client, db, org_admin, org_admin_header, reporter):
        client.put(f"/admin/users/{reporter.id}/entitlements",
                   json={"page_keys": ["dashboard", "stories", "review"]}, headers=org_admin_header)
        resp = client.put(f"/admin/users/{reporter.id}/entitlements",
                          json={"page_keys": ["dashboard"]}, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["entitlements"] == ["dashboard"]
