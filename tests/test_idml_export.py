"""Tests for POST /admin/stories/{story_id}/export-idml."""

import io
import zipfile


# ---------------------------------------------------------------------------
# Sample layout config with masthead, headline, body, and pullquote zones
# ---------------------------------------------------------------------------

SAMPLE_LAYOUT_CONFIG = {
    "width_mm": 380,
    "height_mm": 560,
    "zones": [
        {
            "id": "z-masthead",
            "type": "masthead",
            "label": "NewsFlow Daily",
            "x_mm": 0,
            "y_mm": 0,
            "width_mm": 380,
            "height_mm": 30,
            "columns": 1,
            "column_gap_mm": 0,
            "font_size_pt": 36,
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
            "width_mm": 360,
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
            "width_mm": 360,
            "height_mm": 350,
            "columns": 3,
            "column_gap_mm": 4,
            "font_size_pt": 10,
            "font_family": "serif",
            "bg_color": "#FFFFFF",
            "text_color": "#000000",
            "border_color": "#CCCCCC",
            "text": "",
        },
        {
            "id": "z-pullquote",
            "type": "pullquote",
            "label": "Pullquote",
            "x_mm": 10,
            "y_mm": 450,
            "width_mm": 360,
            "height_mm": 60,
            "columns": 1,
            "column_gap_mm": 0,
            "font_size_pt": 14,
            "font_family": "serif",
            "bg_color": "#EFF6FF",
            "text_color": "#1E40AF",
            "border_color": "#3B82F6",
            "text": "This is an impactful pullquote from the story.",
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_export_idml_returns_zip(client, auth_header, sample_story):
    """POST with sample layout config should return a valid ZIP with required entries."""
    resp = client.post(
        f"/admin/stories/{sample_story.id}/export-idml",
        json={"layout_config": SAMPLE_LAYOUT_CONFIG},
        headers=auth_header,
    )

    assert resp.status_code == 200
    assert "application/octet-stream" in resp.headers.get("content-type", "")

    # Verify it is a valid ZIP
    buf = io.BytesIO(resp.content)
    assert zipfile.is_zipfile(buf)

    buf.seek(0)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()

        # Must contain mimetype
        assert "mimetype" in names

        # Must contain designmap.xml
        assert "designmap.xml" in names

        # Must contain at least one Spread
        spread_files = [n for n in names if n.startswith("Spreads/")]
        assert len(spread_files) >= 1

        # Must contain at least one Story
        story_files = [n for n in names if n.startswith("Stories/")]
        assert len(story_files) >= 1

        # Must contain Styles.xml
        assert "Resources/Styles.xml" in names


def test_export_idml_has_correct_mimetype(client, auth_header, sample_story):
    """The mimetype file inside the IDML ZIP must read the correct IDML MIME type."""
    resp = client.post(
        f"/admin/stories/{sample_story.id}/export-idml",
        json={"layout_config": SAMPLE_LAYOUT_CONFIG},
        headers=auth_header,
    )

    assert resp.status_code == 200

    buf = io.BytesIO(resp.content)
    with zipfile.ZipFile(buf, "r") as zf:
        mimetype_content = zf.read("mimetype").decode("utf-8")
        assert mimetype_content == "application/vnd.adobe.indesign-idml-package"


def test_export_idml_story_not_found(client, auth_header):
    """Request for nonexistent story should return 404."""
    resp = client.post(
        "/admin/stories/nonexistent-id/export-idml",
        json={"layout_config": SAMPLE_LAYOUT_CONFIG},
        headers=auth_header,
    )
    assert resp.status_code == 404


def test_export_idml_content_disposition(client, auth_header, sample_story):
    """Response should include Content-Disposition header with .idml filename."""
    resp = client.post(
        f"/admin/stories/{sample_story.id}/export-idml",
        json={"layout_config": SAMPLE_LAYOUT_CONFIG},
        headers=auth_header,
    )

    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".idml" in cd
