"""Server-side layout renderer using Pillow.

Renders layout zones onto a PNG image for GPT Vision verification.
"""

import io
import logging
import os
import textwrap
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scale and constants
# ---------------------------------------------------------------------------

PX_PER_MM = 2  # render at 2 pixels per mm
PT_TO_PX = PX_PER_MM * 0.3528  # 1pt = 0.3528mm, then to px

_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"

# ---------------------------------------------------------------------------
# Font cache
# ---------------------------------------------------------------------------

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _get_font(family: str = "serif", size_pt: float = 10, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    """Load a TTF font, falling back gracefully."""
    size_px = max(8, int(size_pt * PT_TO_PX))
    cache_key = (family, size_px, bold, italic)
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    # Try to find font file
    candidates = []
    if "odia" in family.lower() or "oriya" in family.lower():
        if bold or italic:
            candidates.append(_FONTS_DIR / "NotoSansOdia-Regular.ttf")
        candidates.append(_FONTS_DIR / "NotoSerifOdia-Regular.ttf")
        candidates.append(_FONTS_DIR / "NotoSansOdia-Regular.ttf")
    elif "sans" in family.lower():
        candidates.append(_FONTS_DIR / "NotoSans-Regular.ttf")
    else:
        candidates.append(_FONTS_DIR / "NotoSerif-Regular.ttf")
        candidates.append(_FONTS_DIR / "NotoSans-Regular.ttf")

    font = None
    for path in candidates:
        if path.exists():
            try:
                font = ImageFont.truetype(str(path), size_px)
                break
            except Exception:
                continue

    if font is None:
        try:
            font = ImageFont.load_default(size_px)
        except TypeError:
            font = ImageFont.load_default()

    _font_cache[cache_key] = font
    return font


# ---------------------------------------------------------------------------
# Text wrapping helper
# ---------------------------------------------------------------------------

def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    lines = []
    current_line = words[0]

    for word in words[1:]:
        test_line = current_line + " " + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)
    return lines


# ---------------------------------------------------------------------------
# Zone drawing functions
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (0, 0, 0)
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def _draw_zone_bg(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, zone: dict):
    bg = zone.get("bg_color", "")
    if bg and bg != "#FFFFFF":
        draw.rectangle([x, y, x + w, y + h], fill=_hex_to_rgb(bg))


def _draw_zone_border(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, dashed: bool = True):
    color = (200, 200, 200)
    draw.rectangle([x, y, x + w, y + h], outline=color, width=1)


def _draw_overflow_indicator(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, overflow_lines: int):
    """Draw red dashed border and overflow badge."""
    draw.rectangle([x, y, x + w, y + h], outline=(220, 38, 38), width=2)
    badge_text = f"+{overflow_lines} lines"
    font = _get_font("sans-serif", 8)
    draw.rectangle([x + w - 60, y + h - 14, x + w, y + h], fill=(220, 38, 38))
    draw.text((x + w - 58, y + h - 13), badge_text, fill=(255, 255, 255), font=font)


def _draw_headline(draw: ImageDraw.ImageDraw, text: str, zone: dict, scale: int):
    x = int(zone["x_mm"] * scale)
    y = int(zone["y_mm"] * scale)
    w = int(zone["width_mm"] * scale)
    h = int(zone["height_mm"] * scale)
    font_size = zone.get("font_size_pt", 28)
    text_color = _hex_to_rgb(zone.get("text_color", "#1C1917"))

    _draw_zone_bg(draw, x, y, w, h, zone)

    font = _get_font(zone.get("font_family", "serif"), font_size, bold=True)
    lines = _wrap_text(draw, text, font, w - 4)
    line_h = int(font_size * PT_TO_PX * 1.2)

    for i, line in enumerate(lines):
        ly = y + i * line_h
        if ly + line_h > y + h:
            break
        draw.text((x + 2, ly), line, fill=text_color, font=font)


def _draw_subheader(draw: ImageDraw.ImageDraw, text: str, zone: dict, scale: int):
    x = int(zone["x_mm"] * scale)
    y = int(zone["y_mm"] * scale)
    w = int(zone["width_mm"] * scale)
    h = int(zone["height_mm"] * scale)
    font_size = zone.get("font_size_pt", 16)
    text_color = _hex_to_rgb(zone.get("text_color", "#44403C"))

    _draw_zone_bg(draw, x, y, w, h, zone)

    font = _get_font(zone.get("font_family", "serif"), font_size)
    lines = _wrap_text(draw, text, font, w - 4)
    line_h = int(font_size * PT_TO_PX * 1.3)

    for i, line in enumerate(lines):
        ly = y + i * line_h
        if ly + line_h > y + h:
            break
        draw.text((x + 2, ly), line, fill=text_color, font=font)


def _draw_body(draw: ImageDraw.ImageDraw, text: str, zone: dict, scale: int) -> int:
    """Draw multi-column body text. Returns number of overflow lines."""
    x = int(zone["x_mm"] * scale)
    y = int(zone["y_mm"] * scale)
    w = int(zone["width_mm"] * scale)
    h = int(zone["height_mm"] * scale)
    cols = max(1, zone.get("columns", 1))
    gap = int(zone.get("column_gap_mm", 4) * scale)
    font_size = zone.get("font_size_pt", 10)
    text_color = _hex_to_rgb(zone.get("text_color", "#1C1917"))

    _draw_zone_bg(draw, x, y, w, h, zone)

    font = _get_font(zone.get("font_family", "serif"), font_size)
    col_width = (w - gap * (cols - 1)) // cols
    line_h = int(font_size * PT_TO_PX * 1.4)
    max_lines_per_col = max(1, h // line_h)

    lines = _wrap_text(draw, text, font, col_width - 4)
    line_idx = 0

    for col in range(cols):
        if line_idx >= len(lines):
            break
        col_x = x + col * (col_width + gap)
        for row in range(max_lines_per_col):
            if line_idx >= len(lines):
                break
            draw.text((col_x + 2, y + row * line_h), lines[line_idx], fill=text_color, font=font)
            line_idx += 1

    overflow = max(0, len(lines) - line_idx)
    if overflow > 0:
        _draw_overflow_indicator(draw, x, y, w, h, overflow)
    return overflow


def _draw_image_zone(draw: ImageDraw.ImageDraw, zone: dict, scale: int, img: Image.Image | None = None, canvas: Image.Image | None = None):
    x = int(zone["x_mm"] * scale)
    y = int(zone["y_mm"] * scale)
    w = int(zone["width_mm"] * scale)
    h = int(zone["height_mm"] * scale)

    if img and canvas:
        # Resize image to fit zone maintaining aspect ratio
        img_ratio = img.width / img.height
        zone_ratio = w / h
        if img_ratio > zone_ratio:
            new_w = w
            new_h = int(w / img_ratio)
        else:
            new_h = h
            new_w = int(h * img_ratio)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        paste_x = x + (w - new_w) // 2
        paste_y = y + (h - new_h) // 2
        canvas.paste(resized, (paste_x, paste_y))
    else:
        draw.rectangle([x, y, x + w, y + h], fill=(245, 245, 244))
        draw.rectangle([x, y, x + w, y + h], outline=(214, 211, 209), width=1)
        font = _get_font("sans-serif", 11)
        label = zone.get("label", "Image")
        draw.text((x + w // 2 - 20, y + h // 2 - 5), label, fill=(168, 162, 158), font=font)


def _draw_masthead(draw: ImageDraw.ImageDraw, text: str, zone: dict, scale: int):
    x = int(zone["x_mm"] * scale)
    y = int(zone["y_mm"] * scale)
    w = int(zone["width_mm"] * scale)
    h = int(zone["height_mm"] * scale)
    font_size = zone.get("font_size_pt", 36)
    text_color = _hex_to_rgb(zone.get("text_color", "#1C1917"))

    _draw_zone_bg(draw, x, y, w, h, zone)

    font = _get_font(zone.get("font_family", "serif"), font_size, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text((x + (w - text_w) // 2, y + 2), text, fill=text_color, font=font)


def _draw_pullquote(draw: ImageDraw.ImageDraw, zone: dict, scale: int):
    x = int(zone["x_mm"] * scale)
    y = int(zone["y_mm"] * scale)
    w = int(zone["width_mm"] * scale)
    h = int(zone["height_mm"] * scale)
    pad = 8

    _draw_zone_bg(draw, x, y, w, h, zone)

    # Left border bar
    border_color = _hex_to_rgb(zone.get("border_color", "#D6D3D1"))
    draw.rectangle([x, y, x + 4, y + h], fill=border_color)

    text = zone.get("text", "")
    if text:
        font_size = zone.get("font_size_pt", 14)
        font = _get_font(zone.get("font_family", "serif"), font_size, italic=True)
        text_color = _hex_to_rgb(zone.get("text_color", "#1C1917"))
        lines = _wrap_text(draw, text, font, w - pad * 2)
        line_h = int(font_size * PT_TO_PX * 1.4)
        for i, line in enumerate(lines):
            ly = y + pad + i * line_h
            if ly + line_h > y + h:
                break
            draw.text((x + pad, ly), line, fill=text_color, font=font)


def _draw_highlight(draw: ImageDraw.ImageDraw, zone: dict, scale: int):
    x = int(zone["x_mm"] * scale)
    y = int(zone["y_mm"] * scale)
    w = int(zone["width_mm"] * scale)
    h = int(zone["height_mm"] * scale)
    pad = 6

    _draw_zone_bg(draw, x, y, w, h, zone)
    border_color = _hex_to_rgb(zone.get("border_color", "#D6D3D1"))
    draw.rectangle([x, y, x + w, y + h], outline=border_color, width=2)

    text = zone.get("text", "")
    if text:
        font_size = zone.get("font_size_pt", 12)
        font = _get_font(zone.get("font_family", "serif"), font_size, bold=True)
        text_color = _hex_to_rgb(zone.get("text_color", "#1C1917"))
        lines = _wrap_text(draw, text, font, w - pad * 2)
        line_h = int(font_size * PT_TO_PX * 1.4)
        for i, line in enumerate(lines):
            ly = y + pad + i * line_h
            if ly + line_h > y + h:
                break
            draw.text((x + pad, ly), line, fill=text_color, font=font)


def _draw_divider(draw: ImageDraw.ImageDraw, zone: dict, scale: int):
    x = int(zone["x_mm"] * scale)
    y = int(zone["y_mm"] * scale)
    w = int(zone["width_mm"] * scale)
    h = int(zone["height_mm"] * scale)
    bg = _hex_to_rgb(zone.get("bg_color", "#D6D3D1"))
    draw.rectangle([x, y, x + w, y + h], fill=bg)


def _draw_sidebar(draw: ImageDraw.ImageDraw, zone: dict, scale: int):
    x = int(zone["x_mm"] * scale)
    y = int(zone["y_mm"] * scale)
    w = int(zone["width_mm"] * scale)
    h = int(zone["height_mm"] * scale)
    pad = 6

    _draw_zone_bg(draw, x, y, w, h, zone)
    border_color = _hex_to_rgb(zone.get("border_color", "#D6D3D1"))
    draw.rectangle([x, y, x + w, y + h], outline=border_color, width=1)

    font_size = zone.get("font_size_pt", 12)
    text_color = _hex_to_rgb(zone.get("text_color", "#1C1917"))
    current_y = y + pad

    if zone.get("label"):
        font = _get_font(zone.get("font_family", "serif"), font_size, bold=True)
        draw.text((x + pad, current_y), zone["label"], fill=text_color, font=font)
        current_y += int(font_size * PT_TO_PX * 1.4)

    text = zone.get("text", "")
    if text:
        body_size = font_size * 0.85
        font = _get_font(zone.get("font_family", "serif"), body_size)
        lines = _wrap_text(draw, text, font, w - pad * 2)
        line_h = int(body_size * PT_TO_PX * 1.4)
        for line in lines:
            if current_y + line_h > y + h:
                break
            draw.text((x + pad, current_y), line, fill=text_color, font=font)
            current_y += line_h


# ---------------------------------------------------------------------------
# Image downloading
# ---------------------------------------------------------------------------

async def _download_image(url: str) -> Image.Image | None:
    """Download an image from a URL, return PIL Image or None."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as exc:
        logger.warning("Failed to download image %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def render_layout_preview(
    layout_config: dict,
    story_data: dict,
) -> bytes:
    """Render layout zones to a PNG image.

    Parameters
    ----------
    layout_config : dict
        {width_mm, height_mm, zones: [...]}
    story_data : dict
        {headline, paragraphs: [{text, type, image_url}], category, ...}

    Returns
    -------
    bytes - PNG image data
    """
    width_mm = layout_config.get("width_mm", 380)
    height_mm = layout_config.get("height_mm", 560)
    zones = layout_config.get("zones", [])
    scale = PX_PER_MM

    img_w = int(width_mm * scale)
    img_h = int(height_mm * scale)

    canvas = Image.new("RGB", (img_w, img_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # Draw page border
    draw.rectangle([0, 0, img_w - 1, img_h - 1], outline=(231, 229, 228), width=1)

    # Prepare story content
    paragraphs = story_data.get("paragraphs", [])
    body_text = " ".join(
        p.get("text", "") if isinstance(p, dict) else str(p)
        for p in paragraphs
        if isinstance(p, dict) and p.get("type") != "image"
    ).strip()

    headline = story_data.get("headline", "")

    # Collect image URLs from paragraphs
    image_urls = [
        p.get("image_url") for p in paragraphs
        if isinstance(p, dict) and (p.get("type") == "image" or p.get("image_url"))
    ]
    image_urls = [u for u in image_urls if u]

    # Pre-download images for image zones
    downloaded_images: list[Image.Image | None] = []
    for url in image_urls:
        downloaded_images.append(await _download_image(url))

    image_idx = 0

    for zone in zones:
        zone_type = zone.get("type", "")
        _draw_zone_border(draw, int(zone["x_mm"] * scale), int(zone["y_mm"] * scale),
                          int(zone["width_mm"] * scale), int(zone["height_mm"] * scale))

        if zone_type == "headline":
            _draw_headline(draw, headline, zone, scale)
        elif zone_type == "subheader":
            sub_text = zone.get("text", "")
            _draw_subheader(draw, sub_text, zone, scale)
        elif zone_type == "body":
            _draw_body(draw, body_text, zone, scale)
        elif zone_type == "image":
            img = None
            if image_idx < len(downloaded_images):
                img = downloaded_images[image_idx]
                image_idx += 1
            _draw_image_zone(draw, zone, scale, img=img, canvas=canvas)
        elif zone_type == "masthead":
            _draw_masthead(draw, zone.get("label", ""), zone, scale)
        elif zone_type == "pullquote":
            _draw_pullquote(draw, zone, scale)
        elif zone_type == "highlight":
            _draw_highlight(draw, zone, scale)
        elif zone_type == "divider":
            _draw_divider(draw, zone, scale)
        elif zone_type == "sidebar":
            _draw_sidebar(draw, zone, scale)

    # Export as PNG
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
