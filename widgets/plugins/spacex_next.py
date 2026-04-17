"""SpaceX next launch via the SpaceX REST API v4."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://api.spacexdata.com/v4/launches/next"


@register
class SpaceXNextWidget(WidgetPlugin):
    id = "spacex_next"
    category = "science"
    template = "spacex_next.html"
    title_en = "SpaceX — Next Launch"
    title_or = "SpaceX — ପରବର୍ତ୍ତୀ ଲଞ୍ଚ"
    dedup_strategy = "deterministic"
    translate_fields = ["details"]
    source_name = "SpaceX REST API"
    source_url = "https://github.com/r-spacex/SpaceX-API"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        return {
            "name": j.get("name") or "",
            "date_utc": j.get("date_utc") or "",
            "flight_number": j.get("flight_number"),
            "details": (j.get("details") or "").strip(),
        }

    def dedup_key(self, payload: dict) -> str:
        return f"spacex-{payload.get('flight_number') or payload.get('name')}"
