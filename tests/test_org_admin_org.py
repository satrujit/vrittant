from app.models.organization import Organization


def _make_test_org(db):
    org = Organization(id="org-test", name="Test Org", slug="test-org", theme_color="#FF0000")
    db.add(org)
    db.commit()
    return org


class TestUpdateOrg:
    def test_org_admin_can_update_org(self, client, db, org_admin, org_admin_header):
        _make_test_org(db)
        resp = client.put("/admin/org", json={"name": "Updated Org", "theme_color": "#00FF00"}, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Org"
        assert resp.json()["theme_color"] == "#00FF00"

    def test_reviewer_cannot_update_org(self, client, db, reviewer, auth_header):
        _make_test_org(db)
        resp = client.put("/admin/org", json={"name": "Hacked"}, headers=auth_header)
        assert resp.status_code == 403

    def test_partial_update(self, client, db, org_admin, org_admin_header):
        _make_test_org(db)
        resp = client.put("/admin/org", json={"theme_color": "#0000FF"}, headers=org_admin_header)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Org"
        assert resp.json()["theme_color"] == "#0000FF"


class TestUploadLogo:
    def test_org_admin_can_upload_logo(self, client, db, org_admin, org_admin_header):
        _make_test_org(db)
        import struct, zlib
        sig = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
        ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
        raw = zlib.compress(b'\x00\x00\x00\x00')
        idat_crc = zlib.crc32(b'IDAT' + raw) & 0xffffffff
        idat = struct.pack('>I', len(raw)) + b'IDAT' + raw + struct.pack('>I', idat_crc)
        iend_crc = zlib.crc32(b'IEND') & 0xffffffff
        iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
        png_bytes = sig + ihdr + idat + iend
        resp = client.put("/admin/org/logo",
                          files={"file": ("logo.png", png_bytes, "image/png")},
                          headers=org_admin_header)
        assert resp.status_code == 200
        assert "/uploads/org-logos/" in resp.json()["logo_url"]
