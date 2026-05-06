"""Pre-processing helpers for inbound WhatsApp text.

Pure functions. No DB, no I/O.
"""
from __future__ import annotations
import re


_FORWARDED_RE = re.compile(r"^>\s*\*?[Ff]orwarded\b.*$")
_QUOTE_LINE_RE = re.compile(r"^>\s.*$")
_WS_RE = re.compile(r"\s+")


def strip_forward_boilerplate(text: str) -> str:
    """Remove leading WhatsApp 'Forwarded from: …' header lines.

    Only consecutive leading quote-lines whose first word is 'Forwarded'
    (case-insensitive, optional asterisks for italic) are stripped. A
    bare quoted-reply line that's NOT a forwarded-marker is preserved.
    """
    if not text:
        return text
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _FORWARDED_RE.match(line):
            i += 1
            # If this is followed by additional quote-lines (no Forwarded
            # keyword), keep stripping them too — they're typically
            # "> Original sender: …" style metadata
            while i < n and _QUOTE_LINE_RE.match(lines[i]):
                i += 1
            break
        else:
            break  # first non-forwarded line — stop scanning
    return "\n".join(lines[i:]).strip()


def word_count(text: str) -> int:
    """Whitespace-delimited word count. Works for Odia and Hindi (which
    use spaces between words just like English)."""
    if not text:
        return 0
    norm = _WS_RE.sub(" ", text).strip()
    if not norm:
        return 0
    return len(norm.split(" "))
