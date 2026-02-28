"""Tests for POST /admin/stories/{story_id}/auto-layout."""

import json
from unittest.mock import AsyncMock, patch


VALID_3_ZONE_RESPONSE = json.dumps({
    "paper_size": "tabloid",
    "width_mm": 280,
    "height_mm": 430,
    "zones": [
        {
            "id": "z-masthead",
            "type": "masthead",
            "label": "Masthead",
            "x_mm": 0,
            "y_mm": 0,
            "width_mm": 280,
            "height_mm": 30,
            "columns": 1,
            "column_gap_mm": 0,
            "font_size_pt": 24,
            "font_family": "serif",
            "bg_color": "#1E40AF",
            "text_color": "#FFFFFF",
            "border_color": "#1E40AF",
            "text": "NewsFlow Daily",
        },
        {
            "id": "z-headline",
            "type": "headline",
            "label": "Main Headline",
            "x_mm": 10,
            "y_mm": 40,
            "width_mm": 260,
            "height_mm": 40,
            "columns": 1,
            "column_gap_mm": 0,
            "font_size_pt": 28,
            "font_family": "serif",
            "bg_color": "#DBEAFE",
            "text_color": "#1E40AF",
            "border_color": "#1E40AF",
            "text": "",
        },
        {
            "id": "z-body",
            "type": "body",
            "label": "Body Text",
            "x_mm": 10,
            "y_mm": 90,
            "width_mm": 260,
            "height_mm": 330,
            "columns": 2,
            "column_gap_mm": 4,
            "font_size_pt": 10,
            "font_family": "serif",
            "bg_color": "#FFFFFF",
            "text_color": "#000000",
            "border_color": "#CCCCCC",
            "text": "",
        },
    ],
})


OVERSIZED_ZONE_RESPONSE = json.dumps({
    "paper_size": "broadsheet",
    "width_mm": 380,
    "height_mm": 560,
    "zones": [
        {
            "id": "z-masthead",
            "type": "masthead",
            "label": "Masthead",
            "x_mm": 0,
            "y_mm": 0,
            "width_mm": 999,
            "height_mm": 30,
            "columns": 1,
            "column_gap_mm": 0,
            "font_size_pt": 24,
            "font_family": "serif",
            "bg_color": "#1E40AF",
            "text_color": "#FFFFFF",
            "border_color": "#1E40AF",
            "text": "",
        },
        {
            "id": "z-headline",
            "type": "headline",
            "label": "Main Headline",
            "x_mm": 10,
            "y_mm": 40,
            "width_mm": 999,
            "height_mm": 999,
            "columns": 1,
            "column_gap_mm": 0,
            "font_size_pt": 28,
            "font_family": "serif",
            "bg_color": "#DBEAFE",
            "text_color": "#1E40AF",
            "border_color": "#1E40AF",
            "text": "",
        },
        {
            "id": "z-body",
            "type": "body",
            "label": "Body Text",
            "x_mm": 500,
            "y_mm": 600,
            "width_mm": 200,
            "height_mm": 200,
            "columns": 3,
            "column_gap_mm": 4,
            "font_size_pt": 10,
            "font_family": "serif",
            "bg_color": "#FFFFFF",
            "text_color": "#000000",
            "border_color": "#CCCCCC",
            "text": "",
        },
    ],
})


@patch("app.routers.layout_ai.call_openai", new_callable=AsyncMock)
def test_auto_layout_returns_zones_and_dimensions(mock_openai, client, auth_header, sample_story):
    """Valid AI response should return page dimensions and zones."""
    mock_openai.return_value = VALID_3_ZONE_RESPONSE

    resp = client.post(
        f"/admin/stories/{sample_story.id}/auto-layout",
        json={},
        headers=auth_header,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_size"] == "tabloid"
    assert data["width_mm"] == 280
    assert data["height_mm"] == 430
    assert "zones" in data
    zones = data["zones"]
    assert len(zones) == 3

    zone_types = {z["type"] for z in zones}
    assert "masthead" in zone_types
    assert "headline" in zone_types
    assert "body" in zone_types

    mock_openai.assert_awaited_once()


@patch("app.routers.layout_ai.call_openai", new_callable=AsyncMock)
def test_auto_layout_validates_bounds(mock_openai, client, auth_header, sample_story):
    """Oversized zones should be clamped to the AI-chosen page dimensions."""
    mock_openai.return_value = OVERSIZED_ZONE_RESPONSE

    resp = client.post(
        f"/admin/stories/{sample_story.id}/auto-layout",
        json={},
        headers=auth_header,
    )

    assert resp.status_code == 200
    data = resp.json()
    page_w = data["width_mm"]
    page_h = data["height_mm"]
    zones = data["zones"]

    for zone in zones:
        assert zone["x_mm"] >= 0
        assert zone["y_mm"] >= 0
        assert zone["x_mm"] + zone["width_mm"] <= page_w
        assert zone["y_mm"] + zone["height_mm"] <= page_h
        assert zone["width_mm"] > 0
        assert zone["height_mm"] > 0


@patch("app.routers.layout_ai.call_openai", new_callable=AsyncMock)
def test_auto_layout_story_not_found(mock_openai, client, auth_header):
    """Request for nonexistent story should return 404."""
    resp = client.post(
        "/admin/stories/nonexistent-id/auto-layout",
        json={},
        headers=auth_header,
    )
    assert resp.status_code == 404
    mock_openai.assert_not_awaited()
