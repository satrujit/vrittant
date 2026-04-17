"""Gita verse-of-the-day — pseudorandom but deterministic per date.

Uses the bhagavadgita.io public mirror (vedabase.io fallback). To avoid
repeats we use ``unique_forever`` on the (chapter, verse) pair.
"""
from __future__ import annotations

import hashlib
from datetime import date

import httpx

from widgets_core import WidgetPlugin, register

# Verse counts per chapter (Bhagavad Gita has 18 chapters)
CHAPTER_VERSE_COUNTS = [
    47, 72, 43, 42, 29, 47, 30, 28, 34, 42,
    55, 20, 35, 27, 20, 24, 28, 78,
]

# Static JSON mirror hosted on GitHub Pages — stable and CORS-friendly
PRIMARY = "https://vedicscriptures.github.io/slok/{chapter}/{verse}/"


def _pick_today() -> tuple[int, int]:
    """Deterministic chapter/verse for today's date."""
    seed = hashlib.sha256(date.today().isoformat().encode()).digest()
    n = int.from_bytes(seed[:4], "big")
    chapter = (n % 18) + 1
    verse = (n // 18) % CHAPTER_VERSE_COUNTS[chapter - 1] + 1
    return chapter, verse


@register
class GitaVerseWidget(WidgetPlugin):
    id = "gita_verse"
    category = "spiritual"
    template = "gita_verse.html"
    title_en = "Gita Verse of the Day"
    title_or = "ଆଜିର ଗୀତା ଶ୍ଳୋକ"
    dedup_strategy = "unique_forever"
    translate_fields = ["english_meaning"]
    source_name = "Vedic Scriptures"
    source_url = "https://vedicscriptures.github.io/"

    async def fetch(self) -> dict:
        chapter, verse = _pick_today()
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(PRIMARY.format(chapter=chapter, verse=verse))
            r.raise_for_status()
            j = r.json()

        sanskrit = j.get("slok") or ""
        # bhagavadgitaapi returns several translations under different author keys
        eng = ""
        for key in ("siva", "purohit", "san"):
            block = j.get(key)
            if isinstance(block, dict) and block.get("et"):
                eng = block["et"]
                break

        return {
            "chapter": chapter,
            "verse": verse,
            "ref": f"{chapter}.{verse}",
            "sanskrit": sanskrit.strip(),
            "transliteration": (j.get("transliteration") or "").strip(),
            "english_meaning": eng.strip(),
        }

    def dedup_key(self, payload: dict) -> str:
        return f"{payload['chapter']}.{payload['verse']}"
