"""Auto-layout: GPT generates HTML for newspaper article layout + IDML export."""

import json
import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_current_org_id
from ..models.layout_template import LayoutTemplate
from ..models.story import Story
from ..models.story_revision import StoryRevision
from ..models.user import User
from ..services.idml_generator import generate_idml
from ..services.openai_client import call_openai
from sqlalchemy.orm import joinedload

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
    instructions: str | None = None
    headline: str | None = None
    paragraphs: list[dict] | None = None
    layout_template_id: str | None = None
    preferences: dict | None = None


# ---------------------------------------------------------------------------
# System prompt — GPT as HTML layout designer
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a **world-class newspaper layout designer**. Given a news article, you produce a single self-contained HTML page that looks like a professionally typeset newspaper article ready for print.

## Output rules
- Return ONLY the raw HTML. No markdown fencing, no explanation.
- The HTML must be a complete document with `<!DOCTYPE html>`, `<html>`, `<head>` (with `<style>`), and `<body>`.
- ALL styles must be in the `<style>` tag in `<head>`. No inline styles.
- Use Google Fonts via `@import` for beautiful typography. Prefer: "Playfair Display" for headlines, "Source Serif 4" or "Lora" for body text, "Noto Sans" or "Noto Serif Odia" for Odia script.
- The page should be designed for a fixed print width (e.g. 280mm / ~1060px). Set `body { max-width: ...; margin: 0 auto; }`.
- Use `@media print` styles so the page prints correctly.

## Design principles
- **Visual hierarchy is everything.** The headline must dominate. Use dramatic size contrast between headline and body text.
- **Priority drives intensity:**
  - BREAKING / URGENT: Massive headline (60-100px), bold accent colors, thick top border or banner, high drama
  - NORMAL: Clean, elegant, traditional newspaper feel
- **Professional typography:** Proper line-height (1.4-1.6 for body), column gaps, letter-spacing on labels, drop caps for the first paragraph of body text
- **Multi-column body text** for longer articles (use CSS `column-count: 2` or `3`)
- **Images** should be prominent — full-width or float with text wrap. Use proper aspect ratio and rounded corners if fitting the design.
- **Bullet points** styled as clean, indented list items with custom markers
- **Pull quotes** in larger italic text with a left accent border
- **Category/priority badges** as small styled labels
- **Byline and dateline** in a clean format below the headline
- **Whitespace** — generous padding and margins for readability
- **Color usage** — use the provided accent/background colors. Dark text on light background. The accent color for borders, dividers, category labels, and headline effects.

## Content structure (use what's appropriate for the story)
1. Category badge / priority label (if breaking/urgent)
2. Headline (largest element on the page)
3. Subheader/deck (2-3 sentence summary in medium-sized text)
4. Byline + dateline
5. Featured image (if present)
6. Body text (multi-column for long articles)
7. Pull quote (pick the most impactful sentence for longer stories)
8. Image captions

## Important
- Handle Odia (ଓଡ଼ିଆ) script — use Noto Serif Odia / Noto Sans Odia font
- If the text is in Odia, import the appropriate Noto Odia font
- Keep images as `<img>` tags with the actual URLs provided
- No JavaScript. Pure HTML + CSS only.
- Make it beautiful. This is for a real newspaper."""

def _clean_html(raw: str) -> str:
    """Strip markdown fencing if GPT wraps the HTML."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:html)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return cleaned.strip()


def _build_preferences_section(preferences: dict | None) -> str:
    """Turn editor design preferences into prompt instructions."""
    if not preferences:
        return ""
    parts = []
    if preferences.get("image_size"):
        size = preferences["image_size"].upper()
        if size == "SMALL":
            parts.append("- Images should be SMALL — use thumbnail-sized images (max 200px wide), floated to the side with text wrapping around them")
        elif size == "LARGE":
            parts.append("- Images should be LARGE — use full-width images spanning the entire content area")
        else:
            parts.append("- Images should be MEDIUM-sized — roughly half the content width")
    if preferences.get("orientation"):
        parts.append(f"- Image orientation: prefer {preferences['orientation']} aspect ratio for all images")
    if preferences.get("columns"):
        parts.append(f"- Use exactly {preferences['columns']} column(s) for body text (override auto column detection)")
    if preferences.get("color_mode") == "bw":
        parts.append("- Use BLACK AND WHITE design ONLY — no colors at all. Monochrome design with grayscale images (use CSS filter: grayscale(100%) on images). Use only black, white, and shades of gray for all elements.")
    if preferences.get("include_subtitle") is False:
        parts.append("- Do NOT include a subtitle/deck/subheader line below the headline")
    if preferences.get("include_bullets") is False:
        parts.append("- Do NOT use bullet points — convert any bulleted content to flowing prose paragraphs")
    if preferences.get("include_quote") is False:
        parts.append("- Do NOT include a pull quote section")
    if parts:
        return "\n## Editor Design Preferences:\n" + "\n".join(parts) + "\n"
    return ""


def _build_template_section(layout_template) -> str:
    """Build the template injection section for the GPT prompt."""
    if not layout_template:
        return ""

    if layout_template.mode == "fixed":
        return f"""
## TEMPLATE MODE: FIXED
You MUST use the following HTML template as the EXACT design reference.
Preserve ALL of the following exactly as-is:
- All CSS styles, colors, backgrounds, gradients, borders
- All fonts, font sizes, font weights, letter-spacing
- The exact layout structure (grid, columns, positioning, spacing)
- All decorative elements (borders, dividers, shapes, background patterns)
- Image placement patterns and sizing approach

Your ONLY job is to replace the placeholder/sample content with the actual article content provided below.
Do NOT change any visual design aspects whatsoever.

<template-html>
{layout_template.html_content}
</template-html>
"""
    else:  # flexible
        return f"""
## TEMPLATE MODE: FLEXIBLE
Use the following HTML template as DESIGN INSPIRATION and structural reference.
You should:
- Follow the same general layout structure (column count, element ordering, section arrangement)
- Maintain the same typographic hierarchy (headline vs subhead vs body proportions)
- Use the story's category accent/background colors instead of the template's colors
- Adapt font sizes, spacing, and proportions to fit the actual content length
- Keep the same general "feel" and design approach but make it work for this specific story

<reference-template>
{layout_template.html_content}
</reference-template>
"""


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
    """Generate an AI-powered newspaper layout as HTML."""

    story = (
        db.query(Story)
        .options(joinedload(Story.revision), joinedload(Story.reporter))
        .filter(Story.id == story_id, Story.organization_id == org_id)
        .first()
    )
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    # Fetch layout template if specified
    layout_template = None
    if body.layout_template_id:
        layout_template = (
            db.query(LayoutTemplate)
            .filter(
                LayoutTemplate.id == body.layout_template_id,
                LayoutTemplate.organization_id == org_id,
            )
            .first()
        )
        if not layout_template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Layout template not found",
            )

    # Use edited content from request if provided, otherwise fall back to DB
    # Check revision first for edited content
    revision = story.revision
    if body.paragraphs is not None:
        paragraphs = body.paragraphs
    elif revision and revision.paragraphs:
        paragraphs = revision.paragraphs
    else:
        paragraphs = story.paragraphs or []

    if body.headline is not None:
        headline_text = body.headline
    elif revision and revision.headline:
        headline_text = revision.headline
    else:
        headline_text = story.headline or ""

    category = (story.category or "general").lower()
    priority = (story.priority or "normal").lower()
    colors = CATEGORY_COLORS.get(category, DEFAULT_COLORS)

    # Build content for GPT
    body_parts = []
    image_urls = []
    for p in paragraphs:
        if isinstance(p, dict):
            p_type = p.get("type", "paragraph")
            p_text = p.get("text", "")
            # Support both image_url and media_path (uploaded images use media_path)
            p_image = p.get("image_url") or p.get("media_path") or ""
            if p_type in ("image", "media") or p_image:
                if p_image:
                    image_urls.append(p_image)
                if p_text:
                    body_parts.append(f"[Image caption: {p_text}]")
            elif p_type == "bullet":
                body_parts.append(f"• {p_text}")
            else:
                body_parts.append(p_text)
        elif isinstance(p, str):
            body_parts.append(p)

    body_text = "\n\n".join(body_parts)
    total_words = len(body_text.split())

    # Reporter info
    reporter_name = ""
    if story.reporter:
        reporter_name = story.reporter.name or ""
    location = story.location or ""

    # Build user prompt
    image_section = ""
    if image_urls:
        urls_list = "\n".join(f"  - {url}" for url in image_urls)
        image_section = f"\nImages (use these exact URLs in <img> tags):\n{urls_list}\n"

    extra_instructions = ""
    if body.instructions:
        extra_instructions = f"\nAdditional instructions from the editor:\n{body.instructions}\n"

    # Build preference and template sections
    preferences_section = _build_preferences_section(body.preferences)
    template_section = _build_template_section(layout_template)

    user_prompt = f"""Design a newspaper article page with the following content:

**Priority:** {priority.upper()}
**Category:** {category}
**Accent color:** {colors['accent']}
**Background color:** {colors['bg']}

**Headline:** {headline_text}

**Reporter:** {reporter_name}
**Location:** {location}
{image_section}
**Article body ({total_words} words):**
{body_text}
{extra_instructions}{preferences_section}{template_section}
Design tips:
- {"This is a BREAKING/URGENT story — make the layout DRAMATIC with oversized headline, bold colors, and high visual impact." if priority in ("urgent", "breaking") else "Use a clean, professional layout appropriate for a " + category + " story."}
- {"Use 2-3 column layout for the body text since this is a longer article." if total_words > 300 else "Single column body is fine for this shorter article."}
- {"Include a pull quote with the most impactful sentence." if total_words > 250 else ""}
- {"Feature the image prominently." if image_urls else "No images for this story."}"""

    logger.info("Generating HTML layout for story %s (%d words, priority=%s, template=%s)",
                story_id, total_words, priority,
                layout_template.name if layout_template else "none")

    # Use higher max_tokens when a template is provided (template HTML consumes input tokens)
    max_tok = 8192 if layout_template else 4096

    try:
        raw_response = await call_openai(SYSTEM_PROMPT, user_prompt, max_tokens=max_tok)
    except httpx.HTTPStatusError as exc:
        logger.error("OpenAI API error: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI layout service returned an error")
    except Exception as exc:
        logger.error("OpenAI call failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI layout service is unavailable")

    html = _clean_html(raw_response)

    if not html.strip().startswith("<!") and not html.strip().startswith("<html"):
        logger.warning("GPT returned non-HTML response, wrapping in basic template")
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{headline_text}</title>
<style>body {{ font-family: serif; max-width: 900px; margin: 0 auto; padding: 40px; }}
h1 {{ font-size: 48px; line-height: 1.1; }} p {{ font-size: 14px; line-height: 1.6; }}</style>
</head><body><h1>{headline_text}</h1>{''.join(f'<p>{p}</p>' for p in body_parts)}</body></html>"""

    logger.info("HTML layout generated for story %s (%d chars)", story_id, len(html))

    response = {"html": html}
    if layout_template:
        response["template_id"] = layout_template.id
        response["template_name"] = layout_template.name
        response["template_mode"] = layout_template.mode
    return response


# ---------------------------------------------------------------------------
# IDML Export
# ---------------------------------------------------------------------------


class ExportIdmlRequest(BaseModel):
    layout_config: dict | None = None


@router.post("/{story_id}/export-idml")
async def export_idml_endpoint(
    story_id: str,
    req: ExportIdmlRequest = ExportIdmlRequest(),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
):
    """Export a story as an InDesign IDML package."""
    story = (
        db.query(Story)
        .options(joinedload(Story.revision), joinedload(Story.reporter))
        .filter(Story.id == story_id, Story.organization_id == org_id)
        .first()
    )
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    # Use revision (edited) content if available
    revision = story.revision
    headline = (revision.headline if revision and revision.headline else story.headline) or ""
    paragraphs = (revision.paragraphs if revision and revision.paragraphs else story.paragraphs) or []

    story_data = {
        "headline": headline,
        "paragraphs": paragraphs,
        "category": story.category or "",
        "priority": story.priority or "normal",
        "reporter": {"name": story.reporter.name if story.reporter else ""},
        "location": story.location or "",
    }

    idml_bytes = await generate_idml(story_data)
    safe_name = re.sub(r'[^\x20-\x7E]', '', story.headline or '')[:50].strip()
    if not safe_name:
        safe_name = 'layout'
    filename = f"{safe_name}-layout.idml"

    return Response(
        content=idml_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
