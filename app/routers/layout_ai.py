"""Auto-layout with visual verification and IDML export for newspaper page layout."""

import base64
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
from ..services.text_measure import (
    estimate_text_height_mm,
    estimate_headline_height_mm,
    calculate_optimal_page_size,
)
from ..services.layout_renderer import render_layout_preview

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
    auto_size: bool = True


# ---------------------------------------------------------------------------
# System prompt for GPT — Creative Art Director
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a **creative newspaper art director**. Given story metrics and
precise text measurements, design a visually compelling single-article page layout.

Return a JSON **object** (no markdown fencing) with these top-level fields:
- paper_size (string: "broadsheet", "tabloid", "compact", or "custom")
- width_mm (number, page width in mm)
- height_mm (number, page height in mm)
- zones (array of zone objects)

## Zone types available
masthead, headline, subheader, body, image, pullquote, highlight, divider, sidebar

## Required zones
- **headline** and **body** are MANDATORY
- **masthead** is OPTIONAL — only include if the story benefits from a publication banner
- **subheader** — a brief deck/summary line between headline and body (recommended)

## Each zone object fields
id (string, unique), type (one of the types above), label (string),
x_mm, y_mm, width_mm, height_mm (numbers — position and size in mm),
columns (integer), column_gap_mm (number),
font_size_pt (number), font_family (string: "serif" or "sans-serif"),
bg_color (hex like "#FFFFFF"), text_color (hex), border_color (hex),
text (string — content for pullquote/highlight/sidebar/subheader zones, empty for others)

## Creative direction
- **Priority is king.** For breaking/urgent stories:
  • Use BOLD, oversized headline fonts (48–80pt or even larger)
  • Dramatic color accents and full-width headline zones
  • Make the page SHOUT — grab eyeballs like a front-page splash
  • Consider a thick accent-colored divider above the headline
- For normal priority: clean, professional, well-balanced layout
- For longer stories (500+ words): use 2–3 column body text, add pullquote with the most impactful sentence
- For stories with images: give images prominent placement (at least 30% of page area)
- Use the category accent and background colors creatively

## Text fitting rules (CRITICAL)
You will receive calculated text measurements. You MUST respect them:
- **body zone height_mm MUST be >= the provided minimum body height**
- **headline zone height_mm MUST be >= the provided minimum headline height**
- If the text won't fit at the chosen font size, INCREASE the zone size or add columns
- Margins: leave at least 8mm on all sides

## Layout creativity
- Vary layouts — don't always use the same grid
- Consider L-shaped text wraps around images
- Use dividers to create visual rhythm
- Sidebars can contain reporter info, location, or related context
- Think like a real newspaper designer — balance whitespace with content density

Return ONLY valid JSON, no explanation."""

# ---------------------------------------------------------------------------
# Vision verification prompt
# ---------------------------------------------------------------------------

VISION_VERIFY_PROMPT = """You are reviewing a rendered newspaper page layout. Analyze this
image for layout quality issues.

Check for:
1. **Text overflow** — is any text cut off at zone edges?
2. **Spacing problems** — are zones too cramped, overlapping, or is there excessive whitespace?
3. **Visual hierarchy** — is the headline prominently sized? Does the eye flow naturally?
4. **Image placement** — are images well-positioned and properly sized?
5. **Overall balance** — does the page feel balanced and professional?

If the layout looks GOOD with no significant issues, respond with:
{"status": "approved", "notes": "brief positive comment"}

If there are issues, respond with:
{"status": "needs_adjustment", "issues": ["specific issue 1", "specific issue 2"],
 "adjustments": [{"zone_id": "...", "field": "height_mm", "value": 150}, ...]}

The adjustments array should contain specific changes: each item has zone_id, field name,
and new value. Only suggest adjustments for real problems.

Return ONLY valid JSON."""

# ---------------------------------------------------------------------------
# OpenAI callers
# ---------------------------------------------------------------------------

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


async def call_openai(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
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
        "temperature": temperature,
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


async def call_openai_vision(system_prompt: str, user_text: str, image_bytes: bytes) -> str:
    """Send an image + text to GPT-4o Vision for analysis."""
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{b64_image}",
                    "detail": "high",
                }},
            ]},
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
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
# JSON parse helper
# ---------------------------------------------------------------------------

def _parse_ai_json(raw: str) -> dict | list:
    """Strip markdown fencing and parse JSON."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Zone validation
# ---------------------------------------------------------------------------

REQUIRED_ZONE_FIELDS = {
    "id", "type", "label", "x_mm", "y_mm", "width_mm", "height_mm",
    "columns", "column_gap_mm", "font_size_pt", "font_family",
    "bg_color", "text_color", "border_color",
}

VALID_ZONE_TYPES = {
    "masthead", "headline", "subheader", "body", "image", "pullquote",
    "highlight", "divider", "sidebar",
}


def validate_zones(zones: list[dict], width_mm: float, height_mm: float) -> list[dict]:
    """Validate and sanitise zones returned by the AI."""
    if not isinstance(zones, list) or len(zones) == 0:
        raise ValueError("Zones must be a non-empty list")

    seen_ids: set[str] = set()
    zone_types_found: set[str] = set()
    validated: list[dict] = []

    for i, zone in enumerate(zones):
        # --- required fields ---
        missing = REQUIRED_ZONE_FIELDS - set(zone.keys())
        if missing:
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

        # Re-clamp after enforcing minimums
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

    # --- require headline + body (masthead is optional) ---
    required_types = {"headline", "body"}
    missing_types = required_types - zone_types_found
    if missing_types:
        raise ValueError(f"Missing required zone types: {', '.join(sorted(missing_types))}")

    return validated


# ---------------------------------------------------------------------------
# Visual verification
# ---------------------------------------------------------------------------

async def verify_layout_with_vision(
    image_bytes: bytes,
    layout_config: dict,
    story_metrics: dict,
) -> dict:
    """Send rendered preview to GPT-4o Vision for analysis.

    Returns dict with "status" ("approved" | "needs_adjustment"),
    optional "issues" list, and optional "adjustments" list.
    """
    context = (
        f"This is a newspaper article layout.\n"
        f"Page: {layout_config.get('width_mm')}mm x {layout_config.get('height_mm')}mm\n"
        f"Story: {story_metrics.get('total_words', 0)} words, "
        f"priority: {story_metrics.get('priority', 'normal')}, "
        f"category: {story_metrics.get('category', 'general')}\n"
        f"Zones: {len(layout_config.get('zones', []))}\n"
        f"Required body height: {story_metrics.get('body_height_needed_mm', 0):.0f}mm\n"
        f"Analyze this layout for issues."
    )
    try:
        raw = await call_openai_vision(VISION_VERIFY_PROMPT, context, image_bytes)
        return _parse_ai_json(raw)
    except Exception as exc:
        logger.warning("Vision verification failed: %s", exc)
        return {"status": "approved", "notes": "Verification skipped due to error"}


def _apply_adjustments(zones: list[dict], adjustments: list[dict]) -> list[dict]:
    """Apply GPT Vision's suggested adjustments to zones."""
    zone_map = {z["id"]: z for z in zones}
    for adj in adjustments:
        zid = adj.get("zone_id", "")
        field = adj.get("field", "")
        value = adj.get("value")
        if zid in zone_map and field in ("x_mm", "y_mm", "width_mm", "height_mm", "font_size_pt", "columns"):
            zone_map[zid][field] = float(value) if value is not None else zone_map[zid][field]
    return list(zone_map.values())


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@router.post("/{story_id}/auto-layout")
async def auto_layout(
    story_id: str,
    body: AutoLayoutRequest = AutoLayoutRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
):
    """Generate an AI-powered newspaper layout with visual verification."""

    # 1. Fetch story
    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    # 2. Compute metrics
    paragraphs = story.paragraphs or []
    headline_text = story.headline or ""
    body_text = " ".join(
        p.get("text", "") for p in paragraphs
        if isinstance(p, dict) and p.get("type") != "image"
    ).strip()
    total_words = len(body_text.split())
    image_count = sum(1 for p in paragraphs if isinstance(p, dict) and (p.get("type") == "image" or p.get("image_url")))
    bullet_count = sum(1 for p in paragraphs if isinstance(p, dict) and p.get("type") == "bullet")
    category = (story.category or "general").lower()
    priority = (story.priority or "normal").lower()
    colors = CATEGORY_COLORS.get(category, DEFAULT_COLORS)

    # 3. Text measurements
    # Choose default font sizes based on priority
    if priority in ("urgent", "breaking"):
        default_headline_pt = 48.0
    else:
        default_headline_pt = 28.0

    default_body_pt = 10.0
    default_body_cols = 2 if total_words > 300 else 1

    # Use user dimensions if provided, otherwise estimate
    page_width = body.width_mm or 380.0

    headline_measure = estimate_headline_height_mm(
        headline_text, font_size_pt=default_headline_pt, width_mm=page_width - 20
    )
    body_measure = estimate_text_height_mm(
        body_text, font_size_pt=default_body_pt,
        column_count=default_body_cols,
        total_width_mm=page_width - 20,
    )

    # 4. Determine page size
    has_user_dimensions = body.width_mm and body.height_mm and not body.auto_size
    if has_user_dimensions:
        page_width = body.width_mm
        page_height = body.height_mm
        paper_size = body.paper_size or "custom"
        dimension_hint = f"FIXED page dimensions: {page_width}mm x {page_height}mm. You MUST use these exact dimensions.\n"
    else:
        paper_size, page_width, page_height = calculate_optimal_page_size(
            body_height_mm=body_measure["height_mm"],
            headline_height_mm=headline_measure["height_mm"],
            image_count=image_count,
            has_pullquote=total_words > 300,
            has_sidebar=total_words > 500,
        )
        dimension_hint = f"Suggested page size: {paper_size} ({page_width}mm x {page_height}mm). You may adjust if needed.\n"

    # 5. Build user prompt with measurements
    para_snippets = "\n".join(
        f"- [{p.get('type', 'text')}] {p.get('text', '')[:200]}" for p in paragraphs
    )

    user_prompt = (
        f"{dimension_hint}\n"
        f"Story priority: **{priority.upper()}**\n"
        f"Category: {category} (accent: {colors['accent']}, bg: {colors['bg']})\n\n"
        f"Story metrics:\n"
        f"  Headline ({len(headline_text)} chars): {headline_text}\n"
        f"  Total words: {total_words}\n"
        f"  Images: {image_count}\n"
        f"  Bullet paragraphs: {bullet_count}\n"
        f"  Paragraphs: {len(paragraphs)}\n\n"
        f"TEXT MEASUREMENTS (you MUST respect these):\n"
        f"  Headline at {default_headline_pt}pt needs minimum {headline_measure['height_mm']}mm height\n"
        f"  Body at {default_body_pt}pt in {default_body_cols} column(s) needs minimum {body_measure['height_mm']}mm height\n"
        f"  If you use different font sizes, adjust zone sizes proportionally.\n\n"
        f"Paragraph previews:\n{para_snippets}"
    )

    # 6. Call GPT for initial layout
    try:
        raw_response = await call_openai(SYSTEM_PROMPT, user_prompt)
    except httpx.HTTPStatusError as exc:
        logger.error("OpenAI API error: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI layout service returned an error")
    except Exception as exc:
        logger.error("OpenAI call failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI layout service is unavailable")

    # 7. Parse response
    try:
        result = _parse_ai_json(raw_response)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse AI response: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI returned invalid JSON")

    # Extract layout data
    if isinstance(result, list):
        zones = result
    elif isinstance(result, dict):
        zones = result.get("zones", [])
        if not has_user_dimensions:
            page_width = float(result.get("width_mm", page_width))
            page_height = float(result.get("height_mm", page_height))
            paper_size = result.get("paper_size", paper_size)
    else:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI returned unexpected format")

    page_width = max(100, min(800, page_width))
    page_height = max(100, min(800, page_height))

    # 8. Validate zones
    try:
        zones = validate_zones(zones, page_width, page_height)
    except ValueError as exc:
        logger.error("Zone validation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI layout validation failed: {exc}")

    # 9. Visual verification loop
    story_data = {
        "headline": headline_text,
        "paragraphs": paragraphs,
        "category": category,
    }
    story_metrics = {
        "total_words": total_words,
        "priority": priority,
        "category": category,
        "body_height_needed_mm": body_measure["height_mm"],
    }

    layout_config = {
        "paper_size": paper_size,
        "width_mm": page_width,
        "height_mm": page_height,
        "zones": zones,
    }

    verification_passes = 0
    max_passes = 3

    for iteration in range(max_passes):
        verification_passes += 1

        # Render preview
        try:
            preview_bytes = await render_layout_preview(layout_config, story_data)
        except Exception as exc:
            logger.warning("Preview render failed at iteration %d: %s", iteration, exc)
            break

        # Send to GPT Vision for verification
        try:
            verdict = await verify_layout_with_vision(preview_bytes, layout_config, story_metrics)
        except Exception as exc:
            logger.warning("Vision verification failed at iteration %d: %s", iteration, exc)
            break

        if verdict.get("status") == "approved":
            logger.info("Layout approved after %d verification pass(es)", verification_passes)
            break

        # Apply adjustments
        adjustments = verdict.get("adjustments", [])
        if not adjustments:
            logger.info("Vision flagged issues but no specific adjustments — accepting layout")
            break

        logger.info("Vision pass %d: applying %d adjustments", iteration + 1, len(adjustments))
        zones = _apply_adjustments(zones, adjustments)

        try:
            zones = validate_zones(zones, page_width, page_height)
        except ValueError:
            logger.warning("Post-adjustment validation failed, keeping previous zones")
            break

        layout_config["zones"] = zones

    return {
        "paper_size": paper_size,
        "width_mm": page_width,
        "height_mm": page_height,
        "zones": zones,
        "verification_passes": verification_passes,
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

    idml_bytes = await generate_idml(req.layout_config, story_data)
    safe_name = re.sub(r'[^\x20-\x7E]', '', story.headline or '')[:50].strip()
    if not safe_name:
        safe_name = 'layout'
    filename = f"{safe_name}-layout.idml"

    return Response(
        content=idml_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
