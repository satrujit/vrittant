"""Quote of the day — ZenQuotes (free, no key, same quote globally per day)."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://zenquotes.io/api/today"


@register
class QuoteOfDayWidget(WidgetPlugin):
    id = "quote_of_day"
    category = "spiritual"
    template = "quote_of_day.html"
    title_en = "Quote of the Day"
    title_or = "ଆଜିର ଉକ୍ତି"
    dedup_strategy = "deterministic"
    translate_fields = ["text"]
    source_name = "ZenQuotes"
    source_url = "https://zenquotes.io/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        first = (j or [{}])[0] if isinstance(j, list) else {}
        return {
            "text": (first.get("q") or "").strip(),
            "author": (first.get("a") or "").strip(),
        }
