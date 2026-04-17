"""Word of the day — curated rotation + Free Dictionary API."""
from __future__ import annotations

from datetime import date

import httpx

from widgets_core import WidgetPlugin, register

# Curated list of substantive English vocabulary; rotates by day-of-year
WORDS = [
    "ephemeral", "serendipity", "ubiquitous", "eloquent", "pragmatic",
    "resilient", "candid", "tenacious", "meticulous", "ambivalent",
    "ineffable", "nuance", "paradigm", "sycophant", "vicarious",
    "quintessential", "pernicious", "magnanimous", "ostentatious", "perfunctory",
    "obsequious", "vehement", "reticent", "voracious", "ephemeral",
    "languid", "fastidious", "ineffable", "epitome", "verisimilitude",
]
URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"


@register
class WordOfDayWidget(WidgetPlugin):
    id = "word_of_day"
    category = "knowledge"
    template = "word_of_day.html"
    title_en = "Word of the Day"
    title_or = "ଆଜିର ଶବ୍ଦ"
    dedup_strategy = "deterministic"
    translate_fields = ["definition", "example"]
    source_name = "Free Dictionary API"
    source_url = "https://dictionaryapi.dev/"

    async def fetch(self) -> dict:
        word = WORDS[date.today().toordinal() % len(WORDS)]
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL.format(word=word))
            r.raise_for_status()
            j = r.json()

        entry = (j or [{}])[0] if isinstance(j, list) else {}
        meanings = entry.get("meanings") or []
        definition = ""
        example = ""
        part = ""
        if meanings:
            m0 = meanings[0]
            part = m0.get("partOfSpeech", "")
            defs = m0.get("definitions") or []
            if defs:
                definition = defs[0].get("definition", "")
                example = defs[0].get("example", "")
        phon = entry.get("phonetic") or ""
        return {
            "word": word,
            "phonetic": phon,
            "part": part,
            "definition": definition,
            "example": example,
        }
