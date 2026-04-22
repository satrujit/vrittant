# AI Auto-Layout + IDML Export — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add GPT-4o-powered automatic newspaper layout generation and full-fidelity IDML (InDesign) package export to the Page Layout tab.

**Architecture:** Backend receives story content, calls OpenAI GPT-4o to generate zone JSON matching existing schema (extended with color + creative zone types). Separate endpoint builds a ZIP-based IDML package from layout config. Frontend adds two buttons to LayoutConfigPanel and extends the canvas renderer to draw new zone types with colors.

**Tech Stack:** Python (FastAPI, httpx, zipfile, xml.etree), OpenAI GPT-4o API, React, HTML5 Canvas API

---

### Task 1: Add OpenAI Config + httpx Dependency

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/config.py:1-12`
- Modify: `/Users/admin/Desktop/newsflow-api/requirements.txt` (or install directly)

**Step 1: Add OPENAI_API_KEY to Settings**

```python
# In config.py, add to Settings class:
OPENAI_API_KEY: str = ""
OPENAI_MODEL: str = "gpt-4o"
```

**Step 2: Install httpx**

Run: `pip3 install httpx`

(httpx is already likely installed as a FastAPI dependency, but ensure it's available)

**Step 3: Verify config loads**

Run: `cd /Users/admin/Desktop/newsflow-api && python3 -c "from app.config import settings; print(settings.OPENAI_API_KEY[:10] if settings.OPENAI_API_KEY else 'NOT SET')"`

**Step 4: Commit**

```bash
git add app/config.py
git commit -m "feat: add OpenAI API key config for auto-layout"
```

---

### Task 2: Auto-Layout Backend Endpoint

**Files:**
- Create: `/Users/admin/Desktop/newsflow-api/app/routers/layout_ai.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/main.py:10` (add import + router)
- Test: `/Users/admin/Desktop/newsflow-api/tests/test_auto_layout.py`

**Step 1: Write the test**

```python
# tests/test_auto_layout.py
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

MOCK_GPT_RESPONSE = {
    "choices": [{
        "message": {
            "content": '[{"id":"zone-masthead","type":"masthead","label":"Newspaper","x_mm":10,"y_mm":10,"width_mm":360,"height_mm":30,"font_size_pt":36,"font_family":"serif"},{"id":"zone-headline","type":"headline","label":"Headline","x_mm":10,"y_mm":50,"width_mm":360,"height_mm":40,"font_size_pt":28,"font_family":"serif"},{"id":"zone-body","type":"body","label":"Body","x_mm":10,"y_mm":100,"width_mm":360,"height_mm":440,"columns":3,"column_gap_mm":4,"font_size_pt":10,"font_family":"serif"}]'
        }
    }]
}


def test_auto_layout_returns_zones(auth_token):
    """Auto-layout endpoint should return validated zones JSON."""
    with patch("app.routers.layout_ai.call_openai", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = MOCK_GPT_RESPONSE
        # Need a valid story ID from DB
        stories = client.get("/admin/stories?offset=0&limit=1").json()
        if stories["total"] == 0:
            pytest.skip("No stories in DB")
        story_id = stories["stories"][0]["id"]

        resp = client.post(
            f"/admin/stories/{story_id}/auto-layout",
            json={"paper_size": "broadsheet", "width_mm": 380, "height_mm": 560},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "zones" in data
        assert len(data["zones"]) >= 3
        assert any(z["type"] == "masthead" for z in data["zones"])
        assert any(z["type"] == "headline" for z in data["zones"])
        assert any(z["type"] == "body" for z in data["zones"])


def test_auto_layout_validates_bounds(auth_token):
    """Zones that exceed page bounds should be clamped."""
    oversized_zone = '[{"id":"zone-body","type":"body","label":"Body","x_mm":10,"y_mm":10,"width_mm":999,"height_mm":999,"columns":1,"font_size_pt":10,"font_family":"serif"},{"id":"zone-masthead","type":"masthead","label":"M","x_mm":10,"y_mm":10,"width_mm":100,"height_mm":30,"font_size_pt":36,"font_family":"serif"},{"id":"zone-headline","type":"headline","label":"H","x_mm":10,"y_mm":50,"width_mm":100,"height_mm":30,"font_size_pt":28,"font_family":"serif"}]'
    with patch("app.routers.layout_ai.call_openai", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = {"choices": [{"message": {"content": oversized_zone}}]}
        stories = client.get("/admin/stories?offset=0&limit=1").json()
        if stories["total"] == 0:
            pytest.skip("No stories in DB")
        story_id = stories["stories"][0]["id"]

        resp = client.post(
            f"/admin/stories/{story_id}/auto-layout",
            json={"paper_size": "broadsheet", "width_mm": 380, "height_mm": 560},
        )
        assert resp.status_code == 200
        zones = resp.json()["zones"]
        for z in zones:
            assert z["x_mm"] + z["width_mm"] <= 380
            assert z["y_mm"] + z["height_mm"] <= 560
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/admin/Desktop/newsflow-api && python3 -m pytest tests/test_auto_layout.py -v`
Expected: FAIL — module `layout_ai` not found

**Step 3: Write the endpoint**

Create `/Users/admin/Desktop/newsflow-api/app/routers/layout_ai.py`:

```python
import json
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models.story import Story

router = APIRouter(prefix="/admin/stories", tags=["layout-ai"])

# ── Category color palettes ──
CATEGORY_COLORS = {
    "politics":      {"accent": "#1E40AF", "bg": "#DBEAFE"},
    "sports":        {"accent": "#166534", "bg": "#DCFCE7"},
    "crime":         {"accent": "#991B1B", "bg": "#FEE2E2"},
    "business":      {"accent": "#92400E", "bg": "#FEF3C7"},
    "entertainment": {"accent": "#6B21A8", "bg": "#F3E8FF"},
}
DEFAULT_COLORS = {"accent": "#374151", "bg": "#F3F4F6"}

SYSTEM_PROMPT = """You are a newspaper page layout designer. Given story metrics and page dimensions, generate an optimal zone layout as a JSON array.

ZONE SCHEMA — each object must have:
- id (string): unique identifier like "zone-masthead", "zone-headline", "zone-body-1"
- type (string): one of "masthead", "headline", "body", "image", "pullquote", "highlight", "divider", "sidebar"
- label (string): descriptive label
- x_mm, y_mm (number): position from top-left in millimeters
- width_mm, height_mm (number): dimensions in millimeters
- columns (number, optional): for body/headline zones, 1-5
- column_gap_mm (number, optional): gap between columns, default 4
- font_size_pt (number): font size in points
- font_family (string): "serif" or "sans-serif"
- bg_color (string, optional): hex background color e.g. "#DBEAFE"
- text_color (string, optional): hex text color e.g. "#1E40AF"
- border_color (string, optional): hex accent border color
- text (string, optional): for pullquote/highlight — the text content to display

LAYOUT RULES:
- Masthead always at top, full page width minus margins, ~30mm height
- Headline below masthead, bold and prominent
- Body text fills the main area, use 2-4 columns for stories over 200 words
- Margins: 10mm on all sides
- Column gap: 4mm minimum between columns
- For stories > 300 words: add a pullquote zone — pick the most impactful sentence from the paragraphs and put it in the "text" field. Use a colored background and left border.
- For stories > 500 words: also add a highlight zone with a key fact or stat, and a sidebar zone if the content warrants it
- Use the provided category colors for accent elements
- Be creative — vary zone positions, don't always use a simple top-to-bottom stack
- Divider zones are thin horizontal bands (5-8mm height) used to visually separate sections
- Maximum 2-3 accent colors per page for visual harmony
- All zones must fit within page bounds (x + width <= page_width, y + height <= page_height)

Return ONLY a valid JSON array. No markdown fencing, no explanation."""


class AutoLayoutRequest(BaseModel):
    paper_size: str = "broadsheet"
    width_mm: float = 380
    height_mm: float = 560


async def call_openai(messages: list[dict]) -> dict:
    """Call OpenAI chat completions API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.OPENAI_MODEL,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4096,
            },
        )
        resp.raise_for_status()
        return resp.json()


def validate_zones(zones: list[dict], width_mm: float, height_mm: float) -> list[dict]:
    """Validate and clamp zones to page bounds."""
    validated = []
    seen_ids = set()
    for z in zones:
        # Ensure required fields
        if not isinstance(z, dict) or "type" not in z:
            continue
        # Unique ID
        zid = z.get("id", f"zone-{len(validated)}")
        if zid in seen_ids:
            zid = f"{zid}-{len(validated)}"
        seen_ids.add(zid)
        z["id"] = zid
        # Clamp positions
        z["x_mm"] = max(0, z.get("x_mm", 10))
        z["y_mm"] = max(0, z.get("y_mm", 10))
        z["width_mm"] = max(20, z.get("width_mm", 100))
        z["height_mm"] = max(5 if z["type"] == "divider" else 20, z.get("height_mm", 50))
        # Clamp to bounds
        if z["x_mm"] + z["width_mm"] > width_mm:
            z["width_mm"] = width_mm - z["x_mm"]
        if z["y_mm"] + z["height_mm"] > height_mm:
            z["height_mm"] = height_mm - z["y_mm"]
        # Validate colors (hex format)
        for color_key in ("bg_color", "text_color", "border_color"):
            val = z.get(color_key)
            if val and not re.match(r'^#[0-9A-Fa-f]{6}$', val):
                del z[color_key]
        validated.append(z)

    # Check required zone types
    types_present = {z["type"] for z in validated}
    if not {"masthead", "headline", "body"} <= types_present:
        raise ValueError("Layout must contain masthead, headline, and body zones")

    return validated


@router.post("/{story_id}/auto-layout")
async def auto_layout(
    story_id: str,
    req: AutoLayoutRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    # Compute metrics
    paragraphs = story.paragraphs or []
    para_texts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in paragraphs]
    total_words = sum(len(t.split()) for t in para_texts)
    headline_chars = len(story.headline or "")
    image_count = sum(1 for p in paragraphs if isinstance(p, dict) and p.get("type") == "image")
    category = (story.category or "general").lower()
    colors = CATEGORY_COLORS.get(category, DEFAULT_COLORS)

    # Build user prompt with paragraph context
    para_summaries = [t[:200] for t in para_texts[:10]]
    user_msg = f"""Page: {req.width_mm}x{req.height_mm}mm ({req.paper_size})
Story: headline="{story.headline}" ({headline_chars} chars)
       {len(paragraphs)} paragraphs, {total_words} words
       {image_count} images, category={category}
Category colors: accent={colors["accent"]}, background={colors["bg"]}

Paragraphs (for context and pullquote selection):
{chr(10).join(f"  {i+1}. {s}" for i, s in enumerate(para_summaries))}"""

    try:
        result = await call_openai([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        content = result["choices"][0]["message"]["content"]
        # Strip any markdown fencing
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```\w*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        zones = json.loads(content)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        raise HTTPException(status_code=502, detail=f"AI returned invalid layout: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {e.response.status_code}")

    try:
        zones = validate_zones(zones, req.width_mm, req.height_mm)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"zones": zones}
```

**Step 4: Register the router in main.py**

In `/Users/admin/Desktop/newsflow-api/app/main.py`, add to the imports line 10:

```python
from .routers import admin, auth, editions, files, layout_ai, sarvam, stories, templates
```

And add the router registration after line 35:

```python
app.include_router(layout_ai.router)
```

**Step 5: Run tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python3 -m pytest tests/test_auto_layout.py -v`
Expected: PASS (with mocked OpenAI)

**Step 6: Commit**

```bash
git add app/routers/layout_ai.py app/main.py tests/test_auto_layout.py
git commit -m "feat: add GPT-4o auto-layout endpoint for newspaper page design"
```

---

### Task 3: IDML Export Backend Endpoint

**Files:**
- Create: `/Users/admin/Desktop/newsflow-api/app/services/idml_generator.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/routers/layout_ai.py` (add export endpoint)
- Test: `/Users/admin/Desktop/newsflow-api/tests/test_idml_export.py`

**Step 1: Write the test**

```python
# tests/test_idml_export.py
import zipfile
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_LAYOUT = {
    "layout_config": {
        "width_mm": 380,
        "height_mm": 560,
        "zones": [
            {"id": "zone-masthead", "type": "masthead", "label": "Test Paper",
             "x_mm": 10, "y_mm": 10, "width_mm": 360, "height_mm": 30,
             "font_size_pt": 36, "font_family": "serif"},
            {"id": "zone-headline", "type": "headline", "label": "Headline",
             "x_mm": 10, "y_mm": 50, "width_mm": 360, "height_mm": 40,
             "font_size_pt": 28, "font_family": "serif"},
            {"id": "zone-body", "type": "body", "label": "Body",
             "x_mm": 10, "y_mm": 100, "width_mm": 360, "height_mm": 400,
             "columns": 3, "column_gap_mm": 4, "font_size_pt": 10, "font_family": "serif"},
            {"id": "zone-pullquote", "type": "pullquote", "label": "Quote",
             "x_mm": 50, "y_mm": 300, "width_mm": 120, "height_mm": 60,
             "font_size_pt": 14, "font_family": "serif",
             "bg_color": "#DBEAFE", "text_color": "#1E40AF", "border_color": "#1E40AF",
             "text": "This is a key quote from the story."},
        ],
    }
}


def test_export_idml_returns_zip():
    """IDML export should return a valid ZIP file."""
    stories = client.get("/admin/stories?offset=0&limit=1").json()
    if stories["total"] == 0:
        import pytest; pytest.skip("No stories")
    story_id = stories["stories"][0]["id"]

    resp = client.post(f"/admin/stories/{story_id}/export-idml", json=SAMPLE_LAYOUT)
    assert resp.status_code == 200
    assert "application/octet-stream" in resp.headers.get("content-type", "")

    # Verify it's a valid ZIP
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    names = z.namelist()
    assert "mimetype" in names
    assert "designmap.xml" in names
    assert any("Spread" in n for n in names)
    assert any("Story" in n for n in names)
    assert any("Styles" in n for n in names)


def test_export_idml_has_correct_mimetype():
    """IDML mimetype must be 'application/vnd.adobe.indesign-idml-package'."""
    stories = client.get("/admin/stories?offset=0&limit=1").json()
    if stories["total"] == 0:
        import pytest; pytest.skip("No stories")
    story_id = stories["stories"][0]["id"]

    resp = client.post(f"/admin/stories/{story_id}/export-idml", json=SAMPLE_LAYOUT)
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    mimetype = z.read("mimetype").decode("utf-8")
    assert mimetype == "application/vnd.adobe.indesign-idml-package"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/admin/Desktop/newsflow-api && python3 -m pytest tests/test_idml_export.py -v`
Expected: FAIL — no `/export-idml` endpoint

**Step 3: Write the IDML generator service**

Create `/Users/admin/Desktop/newsflow-api/app/services/idml_generator.py`:

```python
"""
IDML Package Generator

Generates a valid InDesign IDML (.idml) package from zone layout config
and story content. Uses only Python stdlib (zipfile, xml.etree).

IDML is a ZIP containing XML files:
- mimetype
- META-INF/container.xml
- designmap.xml
- Resources/Styles.xml
- Resources/Graphic.xml
- Spreads/Spread_1.xml
- Stories/Story_{zone_id}.xml (one per text zone)
"""

import io
import re
import zipfile
from xml.sax.saxutils import escape as xml_escape

MM_TO_PT = 2.8346  # 1mm = 2.8346 points


def hex_to_cmyk(hex_color: str) -> tuple[float, float, float, float]:
    """Approximate hex RGB → CMYK conversion."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    k = 1 - max(r, g, b)
    if k == 1:
        return (0, 0, 0, 1)
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    return (round(c, 4), round(m, 4), round(y, 4), round(k, 4))


def _mimetype():
    return "application/vnd.adobe.indesign-idml-package"


def _container_xml():
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<container><rootfiles><rootfile full-path="designmap.xml"/></rootfiles></container>'


def _designmap_xml(story_ids: list[str]):
    stories = "\n".join(f'  <idPkg:Story src="Stories/Story_{sid}.xml"/>' for sid in story_ids)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Document DOMVersion="19.0" xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"
  StoryList="{' '.join(f'u_{sid}' for sid in story_ids)}">
  <idPkg:Graphic src="Resources/Graphic.xml"/>
  <idPkg:Styles src="Resources/Styles.xml"/>
  <idPkg:Spread src="Spreads/Spread_1.xml"/>
{stories}
</Document>"""


def _styles_xml():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Styles xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="19.0">
  <RootParagraphStyleGroup Self="dParagraphStyleGroup">
    <ParagraphStyle Self="ParagraphStyle/$ID/NormalParagraphStyle" Name="$ID/NormalParagraphStyle" FontStyle="Regular" PointSize="10"/>
    <ParagraphStyle Self="ParagraphStyle/Masthead" Name="Masthead" FontStyle="Bold" PointSize="36" Justification="CenterAlign"/>
    <ParagraphStyle Self="ParagraphStyle/Headline" Name="Headline" FontStyle="Bold" PointSize="28"/>
    <ParagraphStyle Self="ParagraphStyle/BodyText" Name="BodyText" FontStyle="Regular" PointSize="10"/>
    <ParagraphStyle Self="ParagraphStyle/Pullquote" Name="Pullquote" FontStyle="Italic" PointSize="14"/>
    <ParagraphStyle Self="ParagraphStyle/Highlight" Name="Highlight" FontStyle="Bold" PointSize="12"/>
    <ParagraphStyle Self="ParagraphStyle/Sidebar" Name="Sidebar" FontStyle="Regular" PointSize="9"/>
  </RootParagraphStyleGroup>
  <RootCharacterStyleGroup Self="dCharacterStyleGroup">
    <CharacterStyle Self="CharacterStyle/$ID/[No character style]" Name="$ID/[No character style]"/>
  </RootCharacterStyleGroup>
</idPkg:Styles>"""


def _graphic_xml(swatches: dict[str, str]):
    """Generate Graphic.xml with color swatches."""
    swatch_entries = []
    for name, hex_color in swatches.items():
        c, m, y, k = hex_to_cmyk(hex_color)
        swatch_entries.append(
            f'  <Color Self="Color/{name}" Name="{name}" Model="Process" Space="CMYK" '
            f'ColorValue="{c*100} {m*100} {y*100} {k*100}"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Graphic xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="19.0">
  <Color Self="Color/Black" Name="Black" Model="Process" Space="CMYK" ColorValue="0 0 0 100"/>
  <Color Self="Color/White" Name="White" Model="Process" Space="CMYK" ColorValue="0 0 0 0"/>
{chr(10).join(swatch_entries)}
</idPkg:Graphic>"""


def _spread_xml(page_w_pt: float, page_h_pt: float, zones: list[dict], story_map: dict):
    """Generate Spread XML with text frames positioned per zone."""
    frames = []
    rect_idx = 0
    for zone in zones:
        x = zone["x_mm"] * MM_TO_PT
        y = zone["y_mm"] * MM_TO_PT
        w = zone["width_mm"] * MM_TO_PT
        h = zone["height_mm"] * MM_TO_PT
        rect_idx += 1
        frame_id = f"rc_{rect_idx}"

        # Background rectangle for zones with bg_color
        bg_color = zone.get("bg_color")
        fill_ref = f'FillColor="Color/{zone["id"]}_bg"' if bg_color else 'FillColor="Color/White"'

        # Column settings
        cols = zone.get("columns", 1)
        col_gap = (zone.get("column_gap_mm", 4)) * MM_TO_PT
        col_attr = f'TextColumnCount="{cols}" TextColumnGutter="{col_gap:.2f}"' if cols > 1 else ""

        # Determine if this zone has a story
        story_ref = story_map.get(zone["id"])
        if story_ref:
            frames.append(f"""    <TextFrame Self="{frame_id}" ParentStory="u_{story_ref}"
      {fill_ref} {col_attr}
      ItemTransform="1 0 0 1 {x:.2f} {y:.2f}">
      <PathGeometry>
        <GeometryPathType PathOpen="false">
          <PathPointArray>
            <PathPointType Anchor="0 0" LeftDirection="0 0" RightDirection="0 0"/>
            <PathPointType Anchor="{w:.2f} 0" LeftDirection="{w:.2f} 0" RightDirection="{w:.2f} 0"/>
            <PathPointType Anchor="{w:.2f} {h:.2f}" LeftDirection="{w:.2f} {h:.2f}" RightDirection="{w:.2f} {h:.2f}"/>
            <PathPointType Anchor="0 {h:.2f}" LeftDirection="0 {h:.2f}" RightDirection="0 {h:.2f}"/>
          </PathPointArray>
        </GeometryPathType>
      </PathGeometry>
    </TextFrame>""")
        else:
            # Non-text zone (divider, image placeholder) — rectangle only
            frames.append(f"""    <Rectangle Self="{frame_id}"
      {fill_ref}
      ItemTransform="1 0 0 1 {x:.2f} {y:.2f}">
      <PathGeometry>
        <GeometryPathType PathOpen="false">
          <PathPointArray>
            <PathPointType Anchor="0 0" LeftDirection="0 0" RightDirection="0 0"/>
            <PathPointType Anchor="{w:.2f} 0" LeftDirection="{w:.2f} 0" RightDirection="{w:.2f} 0"/>
            <PathPointType Anchor="{w:.2f} {h:.2f}" LeftDirection="{w:.2f} {h:.2f}" RightDirection="{w:.2f} {h:.2f}"/>
            <PathPointType Anchor="0 {h:.2f}" LeftDirection="0 {h:.2f}" RightDirection="0 {h:.2f}"/>
          </PathPointArray>
        </GeometryPathType>
      </Rectangle>""")

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Spread xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="19.0">
  <Spread Self="Spread_1" PageCount="1" BindingLocation="0">
    <Page Self="page_1" GeometricBounds="0 0 {page_h_pt:.2f} {page_w_pt:.2f}"
      ItemTransform="1 0 0 1 0 0"/>
{chr(10).join(frames)}
  </Spread>
</idPkg:Spread>"""


def _story_xml(story_id: str, style_name: str, content: str, font_size: float = 10):
    """Generate a Story XML with styled paragraph content."""
    escaped = xml_escape(content)
    paras = escaped.split("\n")
    para_xml = "\n".join(
        f"""    <ParagraphStyleRange AppliedParagraphStyle="ParagraphStyle/{style_name}">
      <CharacterStyleRange AppliedCharacterStyle="CharacterStyle/$ID/[No character style]" PointSize="{font_size}">
        <Content>{p}</Content>
      </CharacterStyleRange>
    </ParagraphStyleRange>"""
        for p in paras if p.strip()
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<idPkg:Story xmlns:idPkg="http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging" DOMVersion="19.0">
  <Story Self="u_{story_id}">
{para_xml}
  </Story>
</idPkg:Story>"""


# Zone type → paragraph style name mapping
ZONE_STYLE_MAP = {
    "masthead": "Masthead",
    "headline": "Headline",
    "body": "BodyText",
    "pullquote": "Pullquote",
    "highlight": "Highlight",
    "sidebar": "Sidebar",
}


def generate_idml(layout_config: dict, story: dict) -> bytes:
    """
    Generate a complete IDML package as bytes.

    Args:
        layout_config: {width_mm, height_mm, zones: [...]}
        story: {headline, paragraphs: [{text}], category, reporter: {name}, location}

    Returns:
        bytes of the .idml ZIP file
    """
    width_mm = layout_config["width_mm"]
    height_mm = layout_config["height_mm"]
    zones = layout_config.get("zones", [])
    page_w_pt = width_mm * MM_TO_PT
    page_h_pt = height_mm * MM_TO_PT

    # Build body text
    paragraphs = story.get("paragraphs", [])
    body_text = "\n".join(
        p.get("text", "") if isinstance(p, dict) else str(p)
        for p in paragraphs
    )

    # Collect color swatches
    swatches = {}
    for zone in zones:
        for ck in ("bg_color", "text_color", "border_color"):
            color = zone.get(ck)
            if color and re.match(r'^#[0-9A-Fa-f]{6}$', color):
                swatches[f"{zone['id']}_{ck.split('_')[0]}"] = color

    # Build stories and story map
    story_map = {}  # zone_id → story_file_id
    story_files = {}  # story_file_id → (style, content, font_size)

    for zone in zones:
        ztype = zone.get("type", "")
        style = ZONE_STYLE_MAP.get(ztype)
        if not style:
            continue  # divider, image — no text content

        sid = zone["id"].replace("-", "_")
        font_size = zone.get("font_size_pt", 10)

        if ztype == "masthead":
            content = zone.get("label", "Newspaper")
        elif ztype == "headline":
            content = story.get("headline", "")
        elif ztype == "body":
            content = body_text
        elif ztype in ("pullquote", "highlight", "sidebar"):
            content = zone.get("text", "")
        else:
            continue

        if content:
            story_map[zone["id"]] = sid
            story_files[sid] = (style, content, font_size)

    # Assemble ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be first and uncompressed
        zf.writestr("mimetype", _mimetype(), compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", _container_xml())
        zf.writestr("designmap.xml", _designmap_xml(list(story_files.keys())))
        zf.writestr("Resources/Styles.xml", _styles_xml())
        zf.writestr("Resources/Graphic.xml", _graphic_xml(swatches))
        zf.writestr("Spreads/Spread_1.xml", _spread_xml(page_w_pt, page_h_pt, zones, story_map))
        for sid, (style, content, font_size) in story_files.items():
            zf.writestr(f"Stories/Story_{sid}.xml", _story_xml(sid, style, content, font_size))

    return buf.getvalue()
```

**Step 4: Add export endpoint to layout_ai.py**

Append to `/Users/admin/Desktop/newsflow-api/app/routers/layout_ai.py`:

```python
from fastapi.responses import Response
from ..services.idml_generator import generate_idml


class ExportIdmlRequest(BaseModel):
    layout_config: dict


@router.post("/{story_id}/export-idml")
async def export_idml(
    story_id: str,
    req: ExportIdmlRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    story_data = {
        "headline": story.headline or "",
        "paragraphs": story.paragraphs or [],
        "category": story.category or "",
        "reporter": {"name": ""},
        "location": story.location or "",
    }
    # Load reporter name if available
    if story.reporter:
        story_data["reporter"]["name"] = story.reporter.name

    idml_bytes = generate_idml(req.layout_config, story_data)
    safe_name = re.sub(r'[^\w\s-]', '', story.headline or 'layout')[:50].strip()
    filename = f"{safe_name}-layout.idml"

    return Response(
        content=idml_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**Step 5: Run tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python3 -m pytest tests/test_idml_export.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add app/services/idml_generator.py app/routers/layout_ai.py tests/test_idml_export.py
git commit -m "feat: add IDML package export for InDesign import"
```

---

### Task 4: Extend Canvas Renderer — New Zone Types + Colors

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/components/PageLayoutPreview/useCanvasRenderer.js:1-177`

**Step 1: Add new draw functions and color support**

Add after `drawMasthead` (line 112), before `renderPage`:

```javascript
function drawPullquote(ctx, zone, scale) {
  const x = zone.x_mm * scale;
  const y = zone.y_mm * scale;
  const w = zone.width_mm * scale;
  const h = zone.height_mm * scale;
  const fontSize = (zone.font_size_pt || 14) * PT_TO_PX;

  // Background
  if (zone.bg_color) {
    ctx.fillStyle = zone.bg_color;
    ctx.fillRect(x, y, w, h);
  }
  // Left accent border
  if (zone.border_color) {
    ctx.fillStyle = zone.border_color;
    ctx.fillRect(x, y, 4 * scale, h);
  }
  // Text
  const text = zone.text || zone.label || '';
  const fontFamily = zone.font_family === 'sans-serif'
    ? "'Noto Sans', 'Plus Jakarta Sans', sans-serif"
    : "'Noto Serif', 'Times New Roman', serif";
  ctx.font = `italic ${fontSize}px ${fontFamily}`;
  ctx.fillStyle = zone.text_color || '#1C1917';
  ctx.textBaseline = 'top';
  const padding = 8 * scale;
  const lines = wrapText(ctx, text, w - padding * 2);
  const lineHeight = fontSize * 1.4;
  lines.forEach((line, i) => {
    if (y + padding + i * lineHeight < y + h - padding) {
      ctx.fillText(line, x + padding, y + padding + i * lineHeight);
    }
  });
}

function drawHighlight(ctx, zone, scale) {
  const x = zone.x_mm * scale;
  const y = zone.y_mm * scale;
  const w = zone.width_mm * scale;
  const h = zone.height_mm * scale;
  const fontSize = (zone.font_size_pt || 12) * PT_TO_PX;

  // Background
  ctx.fillStyle = zone.bg_color || '#F3F4F6';
  ctx.fillRect(x, y, w, h);
  // Border
  if (zone.border_color) {
    ctx.strokeStyle = zone.border_color;
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
  }
  // Text
  const text = zone.text || zone.label || '';
  const fontFamily = zone.font_family === 'sans-serif'
    ? "'Noto Sans', 'Plus Jakarta Sans', sans-serif"
    : "'Noto Serif', 'Times New Roman', serif";
  ctx.font = `bold ${fontSize}px ${fontFamily}`;
  ctx.fillStyle = zone.text_color || '#1C1917';
  ctx.textBaseline = 'top';
  const padding = 6 * scale;
  const lines = wrapText(ctx, text, w - padding * 2);
  const lineHeight = fontSize * 1.4;
  lines.forEach((line, i) => {
    if (y + padding + i * lineHeight < y + h - padding) {
      ctx.fillText(line, x + padding, y + padding + i * lineHeight);
    }
  });
}

function drawDivider(ctx, zone, scale) {
  const x = zone.x_mm * scale;
  const y = zone.y_mm * scale;
  const w = zone.width_mm * scale;
  const h = zone.height_mm * scale;

  ctx.fillStyle = zone.bg_color || '#D6D3D1';
  ctx.fillRect(x, y, w, h);
}

function drawSidebar(ctx, zone, scale) {
  const x = zone.x_mm * scale;
  const y = zone.y_mm * scale;
  const w = zone.width_mm * scale;
  const h = zone.height_mm * scale;
  const fontSize = (zone.font_size_pt || 9) * PT_TO_PX;

  // Background
  ctx.fillStyle = zone.bg_color || '#F5F5F4';
  ctx.fillRect(x, y, w, h);
  // Border
  ctx.strokeStyle = zone.border_color || '#D6D3D1';
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);
  // Title
  const fontFamily = zone.font_family === 'serif'
    ? "'Noto Serif', 'Times New Roman', serif"
    : "'Noto Sans', 'Plus Jakarta Sans', sans-serif";
  ctx.font = `bold ${fontSize * 1.2}px ${fontFamily}`;
  ctx.fillStyle = zone.text_color || '#1C1917';
  ctx.textBaseline = 'top';
  const padding = 6 * scale;
  const labelHeight = fontSize * 1.6;
  ctx.fillText(zone.label || 'Sidebar', x + padding, y + padding);
  // Body text
  const text = zone.text || '';
  if (text) {
    ctx.font = `${fontSize}px ${fontFamily}`;
    const lines = wrapText(ctx, text, w - padding * 2);
    const lineHeight = fontSize * 1.4;
    lines.forEach((line, i) => {
      const ly = y + padding + labelHeight + i * lineHeight;
      if (ly < y + h - padding) {
        ctx.fillText(line, x + padding, ly);
      }
    });
  }
}
```

**Step 2: Update `renderPage` to handle new types and bg_color on existing types**

In `renderPage`, update the zone drawing loop (replace lines 135-161):

```javascript
  const zones = template.zones || [];
  for (const zone of zones) {
    // Draw zone background if bg_color is set (applies to any zone type)
    if (zone.bg_color && zone.type !== 'pullquote' && zone.type !== 'highlight'
        && zone.type !== 'divider' && zone.type !== 'sidebar') {
      ctx.fillStyle = zone.bg_color;
      ctx.fillRect(
        zone.x_mm * scale, zone.y_mm * scale,
        zone.width_mm * scale, zone.height_mm * scale,
      );
    }

    // Dashed border for zones
    ctx.setLineDash([4, 3]);
    ctx.strokeStyle = '#D6D3D1';
    ctx.lineWidth = 0.5;
    ctx.strokeRect(
      zone.x_mm * scale, zone.y_mm * scale,
      zone.width_mm * scale, zone.height_mm * scale,
    );
    ctx.setLineDash([]);

    // Override text color if set
    const savedFillStyle = zone.text_color || null;

    switch (zone.type) {
      case 'headline':
        drawHeadline(ctx, story.headline || '', zone, scale);
        break;
      case 'body':
        drawColumnText(ctx, bodyText, zone, scale);
        break;
      case 'image':
        drawImageZone(ctx, zone, scale);
        break;
      case 'masthead':
        drawMasthead(ctx, zone.label || 'Newspaper', zone, scale);
        break;
      case 'pullquote':
        drawPullquote(ctx, zone, scale);
        break;
      case 'highlight':
        drawHighlight(ctx, zone, scale);
        break;
      case 'divider':
        drawDivider(ctx, zone, scale);
        break;
      case 'sidebar':
        drawSidebar(ctx, zone, scale);
        break;
      default:
        break;
    }
  }
```

**Step 3: Update existing draw functions to respect text_color**

In `drawColumnText` (line 40), change:
```javascript
  ctx.fillStyle = zone.text_color || '#1C1917';
```

In `drawHeadline` (line 70), change:
```javascript
  ctx.fillStyle = zone.text_color || '#1C1917';
```

In `drawMasthead` (line 107), change:
```javascript
  ctx.fillStyle = zone.text_color || '#1C1917';
```

**Step 4: Verify frontend builds**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`
Expected: Build succeeds

**Step 5: Commit**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
git add src/components/PageLayoutPreview/useCanvasRenderer.js
git commit -m "feat: add pullquote, highlight, divider, sidebar zone rendering with color support"
```

---

### Task 5: Update LayoutConfigPanel — Zone Types + Color Fields

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/components/PageLayoutPreview/LayoutConfigPanel.jsx:1-166`

**Step 1: Update ZONE_TYPES constant (line 6)**

```javascript
const ZONE_TYPES = ['headline', 'body', 'image', 'masthead', 'pullquote', 'highlight', 'divider', 'sidebar'];
```

**Step 2: Add color input fields to ZoneEditor**

After the Cols/Font row (line 68), add:

```jsx
        {(zone.type === 'pullquote' || zone.type === 'highlight' || zone.type === 'sidebar') && (
          <>
            <label className={styles.field}>
              <span>Text</span>
              <input value={zone.text || ''} onChange={(e) => update('text', e.target.value)}
                placeholder="Zone text content" />
            </label>
            <div className={styles.fieldRow}>
              <label className={styles.field}>
                <span>BG</span>
                <input type="color" value={zone.bg_color || '#F3F4F6'} onChange={(e) => update('bg_color', e.target.value)} />
              </label>
              <label className={styles.field}>
                <span>Text</span>
                <input type="color" value={zone.text_color || '#1C1917'} onChange={(e) => update('text_color', e.target.value)} />
              </label>
              <label className={styles.field}>
                <span>Border</span>
                <input type="color" value={zone.border_color || '#D6D3D1'} onChange={(e) => update('border_color', e.target.value)} />
              </label>
            </div>
          </>
        )}
        {zone.type === 'divider' && (
          <label className={styles.field}>
            <span>Color</span>
            <input type="color" value={zone.bg_color || '#D6D3D1'} onChange={(e) => update('bg_color', e.target.value)} />
          </label>
        )}
```

**Step 3: Verify build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`

**Step 4: Commit**

```bash
git add src/components/PageLayoutPreview/LayoutConfigPanel.jsx
git commit -m "feat: add new zone types and color config fields to LayoutConfigPanel"
```

---

### Task 6: Frontend API Functions + Auto Layout & Export Buttons

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/services/api.js:290` (add 2 functions)
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/components/PageLayoutPreview/LayoutConfigPanel.jsx` (add buttons)

**Step 1: Add API functions to api.js**

After the templates section (~line 290), add:

```javascript
// ── AI Layout + IDML Export ──

export async function generateAutoLayout(storyId, { paper_size, width_mm, height_mm }) {
  return apiFetch(`/admin/stories/${storyId}/auto-layout`, {
    method: 'POST',
    body: JSON.stringify({ paper_size, width_mm, height_mm }),
  });
}

export async function exportIdml(storyId, layoutConfig) {
  const token = getAuthToken();
  const resp = await fetch(`${API_BASE}/admin/stories/${storyId}/export-idml`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ layout_config: layoutConfig }),
  });
  if (!resp.ok) throw new Error(`Export failed: ${resp.status}`);
  const blob = await resp.blob();
  const filename = resp.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || 'layout.idml';
  // Trigger browser download
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

**Step 2: Add Auto Layout + Export IDML buttons to LayoutConfigPanel**

Update the import line to add new icons and API functions:

```javascript
import { Plus, Trash2, Save, Sparkles, Download, Loader2 } from 'lucide-react';
import { fetchTemplates, createTemplate, generateAutoLayout, exportIdml } from '../../services/api';
```

Add `storyId` to the component props:

```javascript
export default function LayoutConfigPanel({ template, onChange, storyId }) {
```

Add state for loading:

```javascript
  const [autoLayoutLoading, setAutoLayoutLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
```

Add handlers before the return:

```javascript
  const handleAutoLayout = async () => {
    if (!storyId) return;
    setAutoLayoutLoading(true);
    try {
      const result = await generateAutoLayout(storyId, {
        paper_size: template.paper_size || 'broadsheet',
        width_mm: template.width_mm,
        height_mm: template.height_mm,
      });
      onChange({ ...template, zones: result.zones });
    } catch (err) {
      console.error('Auto layout failed:', err);
    } finally {
      setAutoLayoutLoading(false);
    }
  };

  const handleExportIdml = async () => {
    if (!storyId) return;
    setExportLoading(true);
    try {
      await exportIdml(storyId, {
        width_mm: template.width_mm,
        height_mm: template.height_mm,
        zones: template.zones,
      });
    } catch (err) {
      console.error('IDML export failed:', err);
    } finally {
      setExportLoading(false);
    }
  };
```

Add buttons section before the closing `</div>` of the panel (after Save as Template section):

```jsx
      <div className={styles.section}>
        <button
          className={styles.autoLayoutBtn}
          onClick={handleAutoLayout}
          disabled={autoLayoutLoading || !storyId}
        >
          {autoLayoutLoading ? <Loader2 size={14} className={styles.spinner} /> : <Sparkles size={14} />}
          {autoLayoutLoading ? 'Generating...' : 'Auto Layout'}
        </button>
        <button
          className={styles.exportBtn}
          onClick={handleExportIdml}
          disabled={exportLoading || !storyId}
        >
          {exportLoading ? <Loader2 size={14} className={styles.spinner} /> : <Download size={14} />}
          {exportLoading ? 'Exporting...' : 'Export IDML'}
        </button>
      </div>
```

**Step 3: Add button styles to LayoutConfigPanel.module.css**

```css
.autoLayoutBtn {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  background: linear-gradient(135deg, #6366F1, #8B5CF6);
  color: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  margin-bottom: 8px;
  transition: opacity 0.2s;
}
.autoLayoutBtn:hover:not(:disabled) { opacity: 0.9; }
.autoLayoutBtn:disabled { opacity: 0.5; cursor: not-allowed; }

.exportBtn {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #D6D3D1;
  border-radius: 6px;
  background: white;
  color: #1C1917;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}
.exportBtn:hover:not(:disabled) { background: #F5F5F4; }
.exportBtn:disabled { opacity: 0.5; cursor: not-allowed; }

.spinner {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

**Step 4: Verify build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`

**Step 5: Commit**

```bash
git add src/services/api.js src/components/PageLayoutPreview/LayoutConfigPanel.jsx src/components/PageLayoutPreview/LayoutConfigPanel.module.css
git commit -m "feat: add Auto Layout and Export IDML buttons with API integration"
```

---

### Task 7: Pass storyId to LayoutConfigPanel from ReviewPage

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/ReviewPage.jsx:1019`

**Step 1: Update the LayoutConfigPanel usage in ReviewPage**

Find the line (around 1019):
```jsx
              <LayoutConfigPanel
                template={layoutTemplate}
                onChange={setLayoutTemplate}
              />
```

Change to:
```jsx
              <LayoutConfigPanel
                template={layoutTemplate}
                onChange={setLayoutTemplate}
                storyId={id}
              />
```

(`id` is already available from `const { id } = useParams()` at the top of ReviewPage)

**Step 2: Verify build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`

**Step 3: Commit**

```bash
cd /Users/admin/Desktop/newsflow/reviewer-panel
git add src/pages/ReviewPage.jsx
git commit -m "feat: pass storyId to LayoutConfigPanel for auto-layout and export"
```

---

### Task 8: Set OpenAI API Key + Backend Restart

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/config.py` (set the key)

**Step 1: Set the API key in config**

Add the OpenAI API key to the Settings class default (the user provided it during brainstorming).

**Step 2: Restart backend**

```bash
# Kill existing uvicorn
ps aux | grep uvicorn | grep -v grep | awk '{print $2}' | xargs kill
sleep 2
cd /Users/admin/Desktop/newsflow-api
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 2
curl -s http://192.168.1.7:8000/health
```

**Step 3: Verify new endpoints exist**

```bash
curl -s http://192.168.1.7:8000/openapi.json | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d['paths']:
    if 'auto-layout' in p or 'export-idml' in p:
        print(p)
"
```

Expected output:
```
/admin/stories/{story_id}/auto-layout
/admin/stories/{story_id}/export-idml
```

**Step 4: Commit**

```bash
cd /Users/admin/Desktop/newsflow-api
git add app/config.py
git commit -m "feat: configure OpenAI API key for auto-layout"
```

---

### Task 9: Run Full Test Suite + Frontend Build

**Files:** None (verification only)

**Step 1: Run backend tests**

Run: `cd /Users/admin/Desktop/newsflow-api && python3 -m pytest tests/ -v`
Expected: All tests pass

**Step 2: Run frontend build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`
Expected: Build succeeds

**Step 3: End-to-end test in browser**

1. Navigate to a story in the reviewer panel
2. Switch to "Page Layout" tab
3. Click "Auto Layout" button → zones should be generated by GPT and canvas re-renders
4. Click "Export IDML" → `.idml` file should download
5. Open `.idml` in InDesign to verify structure

---

### Task 10: Verify in Browser + Screenshot

**Step 1: Open story in browser**

Navigate to `http://192.168.1.7:5174/review/{story_id}` → click "Page Layout" tab

**Step 2: Test Auto Layout**

Click "Auto Layout" button. Wait for spinner. Canvas should re-render with AI-generated zones including colored pullquotes/highlights.

**Step 3: Test Export IDML**

Click "Export IDML". A `.idml` file should download.

**Step 4: Take screenshot for verification**

Use Playwright or browser screenshot to capture the Page Layout tab with AI-generated layout.
