"""Tests for POST /admin/stories/{story_id}/export-idml."""

import asyncio
import base64
import io
import os
import re
import zipfile
from unittest.mock import patch

from app.services.idml import generate_idml
from app.services.idml.paragraphs import _story_xml

FIXTURE_PIXEL = os.path.join(os.path.dirname(__file__), "fixtures", "pixel.png")


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


# ---------------------------------------------------------------------------
# Bug A — per-script font run splitting
# ---------------------------------------------------------------------------

def _csr_blocks(xml: str) -> list[str]:
    """Return text bodies of each <CharacterStyleRange>...</CharacterStyleRange>."""
    return re.findall(r"<CharacterStyleRange\b[^>]*>(.*?)</CharacterStyleRange>", xml, re.DOTALL)


def _font_of(csr_block: str) -> str | None:
    m = re.search(r"<AppliedFont[^>]*>([^<]+)</AppliedFont>", csr_block)
    return m.group(1) if m else None


def _content_of(csr_block: str) -> str:
    return "".join(re.findall(r"<Content>([^<]*)</Content>", csr_block))


def test_mixed_script_paragraph_splits_into_multiple_runs():
    paras = [{"text": "Hello ନମସ୍କାର World", "point_size": 11,
              "justification": "LeftAlign", "fill_color": "Color/Black",
              "font_style": "Regular"}]
    xml = _story_xml("u201", paras)
    blocks = _csr_blocks(xml)
    assert len(blocks) >= 3, f"expected >=3 CSR blocks, got {len(blocks)}: {blocks}"

    # Find which run contains which text
    found_hello = found_namaskar = found_world = False
    for b in blocks:
        content = _content_of(b)
        font = _font_of(b)
        if "Hello" in content:
            assert font == "Minion Pro", f"Hello run should use Minion Pro, got {font}"
            found_hello = True
        if "ନମସ୍କାର" in content:
            assert font == "Noto Sans Oriya", f"Odia run should use Noto Sans Oriya, got {font}"
            found_namaskar = True
        if "World" in content:
            assert font == "Minion Pro", f"World run should use Minion Pro, got {font}"
            found_world = True
    assert found_hello and found_namaskar and found_world


def test_pure_odia_paragraph_single_noto_run():
    paras = [{"text": "ଓଡ଼ିଆ ବାକ୍ୟ", "point_size": 11,
              "justification": "LeftAlign", "fill_color": "Color/Black",
              "font_style": "Regular"}]
    xml = _story_xml("u201", paras)
    blocks = _csr_blocks(xml)
    assert len(blocks) == 1, f"expected 1 CSR block, got {len(blocks)}"
    assert _font_of(blocks[0]) == "Noto Sans Oriya"


def test_pure_latin_paragraph_single_minion_run():
    paras = [{"text": "Plain English", "point_size": 11,
              "justification": "LeftAlign", "fill_color": "Color/Black",
              "font_style": "Regular"}]
    xml = _story_xml("u201", paras)
    blocks = _csr_blocks(xml)
    assert len(blocks) == 1, f"expected 1 CSR block, got {len(blocks)}"
    assert _font_of(blocks[0]) == "Minion Pro"


# ---------------------------------------------------------------------------
# Bug B — embedded images
# ---------------------------------------------------------------------------

def test_image_embedded_in_idml_zip():
    pixel_bytes = open(FIXTURE_PIXEL, "rb").read()

    async def _fake_download(url: str):
        return pixel_bytes

    story = {
        "headline": "Test",
        "paragraphs": [
            {"type": "paragraph", "text": "Some body text."},
            {"type": "image", "image_url": "https://example.com/pixel.png"},
        ],
        "reporter": {"name": "Tester"},
        "location": "NYC",
        "priority": "normal",
    }

    with patch("app.services.idml.package._download_image", new=_fake_download):
        data = asyncio.run(generate_idml(story))

    buf = io.BytesIO(data)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()

        # No Links/ entries — image is now embedded
        assert not any(n.startswith("Links/") for n in names), \
            f"expected no Links/ entries, got: {[n for n in names if n.startswith('Links/')]}"

        # Spread should include an Image element with embedded contents
        spread = zf.read("Spreads/Spread_ud1.xml").decode("utf-8")
        assert "<Image " in spread
        assert "$ID/Embedded" in spread
        assert "<Contents>" in spread

        # Extract base64 contents and verify they decode to the original image
        m = re.search(r"<Contents>([^<]+)</Contents>", spread)
        assert m, "no <Contents> found in spread XML"
        decoded = base64.b64decode(m.group(1))
        assert decoded == pixel_bytes
