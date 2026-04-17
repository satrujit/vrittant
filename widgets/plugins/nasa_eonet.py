"""NASA EONET — open natural events (wildfires, storms, volcanoes)."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=8&days=20"


@register
class NasaEonetWidget(WidgetPlugin):
    id = "nasa_eonet"
    category = "science"
    template = "nasa_eonet.html"
    title_en = "Natural Events (NASA EONET)"
    title_or = "ପ୍ରାକୃତିକ ଘଟଣା (NASA EONET)"
    dedup_strategy = "none"
    source_name = "NASA EONET"
    source_url = "https://eonet.gsfc.nasa.gov/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        rows = []
        for ev in (j.get("events") or [])[:6]:
            cat = (ev.get("categories") or [{}])[0].get("title", "")
            rows.append({
                "title": ev.get("title", ""),
                "category": cat,
            })
        return {"rows": rows}
