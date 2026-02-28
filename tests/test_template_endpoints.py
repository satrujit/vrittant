SAMPLE_TEMPLATE = {
    "name": "Front Page",
    "paper_size": "broadsheet",
    "width_mm": 380.0,
    "height_mm": 560.0,
    "zones": [
        {
            "id": "z1", "type": "headline",
            "x_mm": 20, "y_mm": 40, "width_mm": 170, "height_mm": 30,
            "columns": 1, "column_gap_mm": 4,
            "font_size_pt": 28, "font_family": "serif", "label": "Main Headline",
        },
        {
            "id": "z2", "type": "body",
            "x_mm": 20, "y_mm": 80, "width_mm": 340, "height_mm": 400,
            "columns": 3, "column_gap_mm": 4,
            "font_size_pt": 10, "font_family": "serif", "label": "Body Text",
        },
    ],
}


def test_create_template(client, auth_header):
    resp = client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Front Page"
    assert len(data["zones"]) == 2
    assert data["id"] is not None


def test_list_templates(client, auth_header):
    client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    resp = client.get("/admin/templates", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Front Page"


def test_get_template(client, auth_header):
    create_resp = client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    tpl_id = create_resp.json()["id"]
    resp = client.get(f"/admin/templates/{tpl_id}", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Front Page"


def test_update_template(client, auth_header):
    create_resp = client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    tpl_id = create_resp.json()["id"]
    resp = client.put(
        f"/admin/templates/{tpl_id}",
        json={"name": "Updated Name"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert len(resp.json()["zones"]) == 2


def test_delete_template(client, auth_header):
    create_resp = client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    tpl_id = create_resp.json()["id"]
    resp = client.delete(f"/admin/templates/{tpl_id}", headers=auth_header)
    assert resp.status_code == 204
    get_resp = client.get(f"/admin/templates/{tpl_id}", headers=auth_header)
    assert get_resp.status_code == 404
