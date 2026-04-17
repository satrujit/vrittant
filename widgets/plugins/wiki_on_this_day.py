"""Wikipedia "on this day" — selected events for today's date."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected/{m:02d}/{d:02d}"
_IST = timezone(timedelta(hours=5, minutes=30))


@register
class WikiOnThisDayWidget(WidgetPlugin):
    id = "wiki_on_this_day"
    category = "knowledge"
    template = "wiki_on_this_day.html"
    title_en = "Wikipedia — On This Day"
    title_or = "ୱିକିପିଡ଼ିଆ — ଆଜିର ଦିନରେ"
    dedup_strategy = "deterministic"
    timeout_seconds = 60
    translate_fields = ["events.*.text"]
    source_name = "Wikimedia"
    source_url = "https://en.wikipedia.org/wiki/Wikipedia:On_this_day"

    async def fetch(self) -> dict:
        now = datetime.now(_IST)
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Vrittant/1.0 (https://vrittant.in; contact@vrittant.in)",
                "Accept": "application/json",
            },
        ) as client:
            r = await client.get(URL.format(m=now.month, d=now.day))
            r.raise_for_status()
            j = r.json()

        events = []
        for e in (j.get("selected") or [])[:8]:
            events.append({
                "year": e.get("year"),
                "text": (e.get("text") or "").strip(),
            })
        return {
            "label": now.strftime("%d %B"),
            "events": events,
        }

    def dedup_key(self, payload: dict) -> str:
        return f"wiki-otd-{payload.get('label', '')}"
