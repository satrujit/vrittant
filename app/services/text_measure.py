"""Text measurement utilities for newspaper layout.

Estimates how much vertical space text requires given font size,
column configuration, and script type (Latin vs Odia).
"""

import math
import re

# 1 pt = 0.3528 mm
PT_TO_MM = 0.3528

# Average character width as a fraction of font size (in pt).
# Odia glyphs are wider on average than Latin.
_CHAR_WIDTH_FACTOR_LATIN = 0.55
_CHAR_WIDTH_FACTOR_ODIA = 0.65

# Simple heuristic: if >30% of chars are non-ASCII, treat as Odia
_NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")


def _is_odia(text: str) -> bool:
    if not text:
        return False
    non_ascii = len(_NON_ASCII_RE.findall(text))
    return non_ascii / max(len(text), 1) > 0.3


def estimate_text_height_mm(
    text: str,
    font_size_pt: float = 10.0,
    column_count: int = 1,
    total_width_mm: float = 360.0,
    column_gap_mm: float = 4.0,
    line_height_mult: float = 1.4,
    is_odia: bool | None = None,
) -> dict:
    """Estimate how many mm of vertical space *text* needs.

    Returns
    -------
    dict with keys:
        total_chars, chars_per_line, total_lines, lines_per_column,
        height_mm, font_size_pt, columns
    """
    if is_odia is None:
        is_odia = _is_odia(text)

    char_w_factor = _CHAR_WIDTH_FACTOR_ODIA if is_odia else _CHAR_WIDTH_FACTOR_LATIN
    char_width_mm = font_size_pt * char_w_factor * PT_TO_MM

    col_width_mm = (total_width_mm - column_gap_mm * max(column_count - 1, 0)) / max(column_count, 1)
    chars_per_line = max(1, int(col_width_mm / char_width_mm))

    total_chars = len(text)
    total_lines = max(1, math.ceil(total_chars / chars_per_line))
    lines_per_column = max(1, math.ceil(total_lines / max(column_count, 1)))

    line_height_mm = font_size_pt * line_height_mult * PT_TO_MM
    height_mm = lines_per_column * line_height_mm

    return {
        "total_chars": total_chars,
        "chars_per_line": chars_per_line,
        "total_lines": total_lines,
        "lines_per_column": lines_per_column,
        "height_mm": round(height_mm, 1),
        "font_size_pt": font_size_pt,
        "columns": column_count,
    }


def estimate_headline_height_mm(
    text: str,
    font_size_pt: float = 28.0,
    width_mm: float = 360.0,
    line_height_mult: float = 1.2,
    is_odia: bool | None = None,
) -> dict:
    """Estimate height for a headline (single column, larger font)."""
    return estimate_text_height_mm(
        text=text,
        font_size_pt=font_size_pt,
        column_count=1,
        total_width_mm=width_mm,
        column_gap_mm=0,
        line_height_mult=line_height_mult,
        is_odia=is_odia,
    )


def calculate_optimal_page_size(
    body_height_mm: float,
    headline_height_mm: float,
    image_count: int = 0,
    has_pullquote: bool = False,
    has_sidebar: bool = False,
    margin_mm: float = 10.0,
) -> tuple[str, float, float]:
    """Pick the smallest standard page size that fits all content.

    Returns (paper_size_name, width_mm, height_mm).
    """
    # Estimate total height needed
    extra = 0.0
    if image_count > 0:
        extra += 80 * image_count  # ~80mm per image
    if has_pullquote:
        extra += 40
    if has_sidebar:
        extra += 60

    total_height = headline_height_mm + body_height_mm + extra + margin_mm * 2 + 10  # 10mm buffer

    # Standard sizes (width, height)
    sizes = [
        ("compact", 250, 350),
        ("tabloid", 280, 430),
        ("broadsheet", 380, 560),
    ]

    for name, w, h in sizes:
        if total_height <= h:
            return (name, float(w), float(h))

    # Content too tall for broadsheet — use custom height
    return ("custom", 380.0, round(max(560, total_height + 20), 0))
