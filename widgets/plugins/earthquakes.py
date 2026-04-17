"""Significant earthquakes in the last 24h via USGS."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"


@register
class EarthquakesWidget(WidgetPlugin):
    id = "earthquakes"
    category = "science"
    template = "earthquakes.html"
    title_en = "Recent Earthquakes (M4.5+)"
    title_or = "ସାମ୍ପ୍ରତିକ ଭୂମିକମ୍ପ (M୪.୫+)"
    dedup_strategy = "none"
    source_name = "USGS"
    source_url = "https://earthquake.usgs.gov/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        features = j.get("features") or []
        # Sort by magnitude desc, take top 6
        features.sort(key=lambda f: f.get("properties", {}).get("mag") or 0, reverse=True)
        rows = []
        for f in features[:6]:
            p = f.get("properties", {})
            ts = p.get("time")
            when = ""
            if ts:
                when = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%d %b %H:%M UTC")
            rows.append({
                "mag": p.get("mag"),
                "place": p.get("place") or "",
                "time": when,
            })
        return {"rows": rows}
