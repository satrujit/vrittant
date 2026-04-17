"""Shared constants and small helpers for the IDML generator package."""

import re

DOM_VERSION = "21.2"
NS = "http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging"

PAGE_W_PT = 612.0   # US Letter
PAGE_H_PT = 792.0
MARGIN_PT = 36.0
CONTENT_W = PAGE_W_PT - 2 * MARGIN_PT   # 540
CONTENT_H = PAGE_H_PT - 2 * MARGIN_PT   # 720
COL_GAP_PT = 12.0

# Odia Unicode block: U+0B00 – U+0B7F
_ODIA_RE = re.compile(r"[\u0B00-\u0B7F]")

ODIA_FONT = "Noto Sans Oriya"
LATIN_FONT = "Minion Pro"


def _is_odia(text: str) -> bool:
    """Return True if text contains Odia script characters."""
    return bool(_ODIA_RE.search(text))
