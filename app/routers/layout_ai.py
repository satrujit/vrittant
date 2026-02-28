"""Auto-layout and IDML export endpoints for newspaper page layout."""

import json
import logging
import re
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_current_org_id
from ..models.story import Story
from ..models.user import User
from ..services.idml_generator import generate_idml

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/stories", tags=["layout-ai"])

# ---------------------------------------------------------------------------
# Category colour palettes
# ---------------------------------------------------------------------------

CATEGORY_COLORS = {
    "politics":      {"accent": "#1E40AF", "bg": "#DBEAFE"},
    "sports":        {"accent": "#166534", "bg": "#DCFCE7"},
    "crime":         {"accent": "#991B1B", "bg": "#FEE2E2"},
    "business":      {"accent": "#92400E", "bg": "#FEF3C7"},
    "entertainment": {"accent": "#6B21A8", "bg": "#F3E8FF"},
}
DEFAULT_COLORS = {"accent": "#374151", "bg": "#F3F4F6"}

# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class AutoLayoutRequest(BaseModel):
    paper_size: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None


# ---------------------------------------------------------------------------
# System prompt for GPT
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a newspaper layout engine. Given story metrics, choose the
optimal page size and generate layout zones for a single newspaper page.

Return a JSON **object** (not an array) with these top-level fields:
- paper_size (string, one of: "broadsheet", "tabloid", "compact", "custom")
- width_mm (number, page width in mm)
- height_mm (number, page height in mm)
- zones (array of zone objects)

Page size guidelines:
- Short stories (under 150 words): use compact (250mm x 350mm) or tabloid (280mm x 430mm)
- Medium stories (150-500 words): use tabloid (280mm x 430mm)
- Long stories (over 500 words): use broadsheet (380mm x 560mm)
- If the user provides fixed dimensions, use those instead

Each zone object must have these fields:
- id (string, unique)
- type (one of: masthead, headline, body, image, pullquote, highlight, divider, sidebar)
- label (string, human-readable name)
- x_mm (number, left edge in mm)
- y_mm (number, top edge in mm)
- width_mm (number, zone width in mm)
- height_mm (number, zone height in mm)
- columns (integer, number of text columns, 1 for non-text zones)
- column_gap_mm (number, gap between columns in mm)
- font_size_pt (number, font size in points)
- font_family (string, e.g. "serif", "sans-serif")
- bg_color (string, hex color like "#FFFFFF")
- text_color (string, hex color like "#000000")
- border_color (string, hex color like "#CCCCCC")
- text (string, optional text content for the zone, empty string if none)

Layout rules:
- Masthead zone at top, full width, approximately 30mm tall
- Margins of 10mm on all sides
- For stories over 300 words: add a pullquote zone (pick the most impactful sentence from the paragraphs and put it in the "text" field)
- For stories over 500 words: add a highlight zone and a sidebar zone
- Use the provided category accent and background colors for styling
- Be creative with the layout while maintaining readability
- All zones must fit within the chosen page dimensions
- Return ONLY a valid JSON object, no markdown fencing, no explanation"""

# ---------------------------------------------------------------------------
# OpenAI caller
# ---------------------------------------------------------------------------

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


async def call_openai(system_prompt: str, user_prompt: str) -> str:
    """POST to OpenAI chat completions and return the assistant message content."""
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Zone validation
# ---------------------------------------------------------------------------

REQUIRED_ZONE_FIELDS = {
    "id", "type", "label", "x_mm", "y_mm", "width_mm", "height_mm",
    "columns", "column_gap_mm", "font_size_pt", "font_family",
    "bg_color", "text_color", "border_color",
}

VALID_ZONE_TYPES = {
    "masthead", "headline", "body", "image", "pullquote",
    "highlight", "divider", "sidebar",
}


def validate_zones(zones: list[dict], width_mm: float, height_mm: float) -> list[dict]:
    """Validate and sanitise zones returned by the AI.

    - Ensures required fields exist
    - Unique IDs
    - Clamps positions/sizes to page bounds
    - Validates hex colour format
    - Enforces minimum sizes
    - Requires at least masthead + headline + body
    """
    if not isinstance(zones, list) or len(zones) == 0:
        raise ValueError("Zones must be a non-empty list")

    seen_ids: set[str] = set()
    zone_types_found: set[str] = set()
    validated: list[dict] = []

    for i, zone in enumerate(zones):
        # --- required fields ---
        missing = REQUIRED_ZONE_FIELDS - set(zone.keys())
        if missing:
            # Fill in sensible defaults for missing optional-ish fields
            for field in missing:
                if field in ("bg_color", "text_color", "border_color"):
                    zone[field] = "#000000"
                elif field in ("columns", "column_gap_mm", "font_size_pt"):
                    zone[field] = 1 if field == "columns" else (4 if field == "column_gap_mm" else 10)
                elif field == "font_family":
                    zone[field] = "serif"
                elif field == "label":
                    zone[field] = zone.get("type", f"zone-{i}")
                elif field == "id":
                    zone["id"] = str(uuid.uuid4())[:8]
                else:
                    zone[field] = 0

        # --- ensure text field exists ---
        if "text" not in zone:
            zone["text"] = ""

        # --- unique IDs ---
        zid = str(zone["id"])
        if zid in seen_ids:
            zid = f"{zid}-{uuid.uuid4().hex[:4]}"
        zone["id"] = zid
        seen_ids.add(zid)

        # --- type check ---
        if zone.get("type") in VALID_ZONE_TYPES:
            zone_types_found.add(zone["type"])

        # --- clamp positions and sizes to page bounds ---
        zone["x_mm"] = max(0, min(float(zone["x_mm"]), width_mm))
        zone["y_mm"] = max(0, min(float(zone["y_mm"]), height_mm))
        zone["width_mm"] = max(0, min(float(zone["width_mm"]), width_mm - zone["x_mm"]))
        zone["height_mm"] = max(0, min(float(zone["height_mm"]), height_mm - zone["y_mm"]))

        # --- minimum sizes ---
        min_size = 5 if zone.get("type") == "divider" else 20
        zone["width_mm"] = max(zone["width_mm"], min_size)
        zone["height_mm"] = max(zone["height_mm"], min_size)

        # Re-clamp after enforcing minimums (to stay within page)
        if zone["x_mm"] + zone["width_mm"] > width_mm:
            zone["x_mm"] = max(0, width_mm - zone["width_mm"])
        if zone["y_mm"] + zone["height_mm"] > height_mm:
            zone["y_mm"] = max(0, height_mm - zone["height_mm"])

        # --- validate hex colours ---
        for colour_field in ("bg_color", "text_color", "border_color"):
            val = zone.get(colour_field, "")
            if not isinstance(val, str) or not _HEX_COLOR_RE.match(val):
                zone[colour_field] = "#000000"

        validated.append(zone)

    # --- require at least masthead + headline + body ---
    required_types = {"masthead", "headline", "body"}
    missing_types = required_types - zone_types_found
    if missing_types:
        raise ValueError(f"Missing required zone types: {', '.join(sorted(missing_types))}")

    return validated


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/{story_id}/auto-layout")
async def auto_layout(
    story_id: str,
    body: AutoLayoutRequest = AutoLayoutRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
):
    """Generate an AI-powered newspaper layout for a story."""

    # 1. Fetch story
    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found",
        )

    # 2. Compute metrics
    paragraphs = story.paragraphs or []
    paragraph_count = len(paragraphs)
    headline_chars = len(story.headline or "")
    total_words = sum(
        len(p.get("text", "").split()) for p in paragraphs
    )
    image_count = sum(
        1 for p in paragraphs if p.get("type") == "image" or p.get("image_url")
    )
    category = (story.category or "general").lower()
    colors = CATEGORY_COLORS.get(category, DEFAULT_COLORS)

    # 3. Build user prompt
    para_snippets = "\n".join(
        f"- {p.get('text', '')[:200]}" for p in paragraphs
    )

    # If user provided fixed dimensions, tell GPT to use them
    dimension_hint = ""
    if body.width_mm and body.height_mm:
        dimension_hint = f"Use fixed page dimensions: {body.width_mm}mm x {body.height_mm}mm ({body.paper_size or 'custom'})\n"

    user_prompt = (
        f"{dimension_hint}"
        f"Story metrics:\n"
        f"  - Headline ({headline_chars} chars): {story.headline}\n"
        f"  - Paragraphs: {paragraph_count}\n"
        f"  - Total words: {total_words}\n"
        f"  - Images: {image_count}\n"
        f"  - Category: {category}\n"
        f"  - Accent color: {colors['accent']}\n"
        f"  - Background color: {colors['bg']}\n"
        f"\nParagraph previews:\n{para_snippets}"
    )

    # 4. Call OpenAI
    try:
        raw_response = await call_openai(SYSTEM_PROMPT, user_prompt)
    except httpx.HTTPStatusError as exc:
        logger.error("OpenAI API error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI layout service returned an error",
        )
    except Exception as exc:
        logger.error("OpenAI call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI layout service is unavailable",
        )

    # 5. Parse response — strip markdown fencing if present
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse AI response as JSON: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned invalid JSON",
        )

    # 6. Extract page dimensions and zones from response
    # Support both old format (array of zones) and new format (object with dimensions + zones)
    if isinstance(result, list):
        # Old format: just an array of zones — use defaults
        zones = result
        page_width = body.width_mm or 380
        page_height = body.height_mm or 560
        paper_size = body.paper_size or "broadsheet"
    elif isinstance(result, dict):
        zones = result.get("zones", [])
        page_width = float(result.get("width_mm", body.width_mm or 380))
        page_height = float(result.get("height_mm", body.height_mm or 560))
        paper_size = result.get("paper_size", body.paper_size or "broadsheet")
    else:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned unexpected format",
        )

    # Sanity-check page dimensions (minimum 100mm, maximum 800mm)
    page_width = max(100, min(800, page_width))
    page_height = max(100, min(800, page_height))

    # 7. Validate zones against the (possibly AI-chosen) page dimensions
    try:
        zones = validate_zones(zones, page_width, page_height)
    except ValueError as exc:
        logger.error("Zone validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI layout validation failed: {exc}",
        )

    return {
        "paper_size": paper_size,
        "width_mm": page_width,
        "height_mm": page_height,
        "zones": zones,
    }


# ---------------------------------------------------------------------------
# IDML Export
# ---------------------------------------------------------------------------


class ExportIdmlRequest(BaseModel):
    layout_config: dict


@router.post("/{story_id}/export-idml")
async def export_idml(
    story_id: str,
    req: ExportIdmlRequest,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
):
    """Export a story layout as an InDesign IDML package."""
    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    story_data = {
        "headline": story.headline or "",
        "paragraphs": story.paragraphs or [],
        "category": story.category or "",
        "reporter": {"name": story.reporter.name if story.reporter else ""},
        "location": story.location or "",
    }

    idml_bytes = generate_idml(req.layout_config, story_data)
    safe_name = re.sub(r'[^\x20-\x7E]', '', story.headline or '')[:50].strip()
    if not safe_name:
        safe_name = 'layout'
    filename = f"{safe_name}-layout.idml"

    return Response(
        content=idml_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
