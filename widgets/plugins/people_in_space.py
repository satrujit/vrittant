"""People currently in space via Open Notify."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = "http://api.open-notify.org/astros.json"


@register
class PeopleInSpaceWidget(WidgetPlugin):
    id = "people_in_space"
    category = "science"
    template = "people_in_space.html"
    title_en = "People in Space"
    title_or = "ଅନ୍ତରୀକ୍ଷରେ ଲୋକ"
    dedup_strategy = "deterministic"
    timeout_seconds = 90
    translate_fields = ["crafts.*.people"]
    source_name = "Open Notify"
    source_url = "http://open-notify.org/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        people = j.get("people") or []
        # Group by craft
        by_craft: dict[str, list[str]] = {}
        for p in people:
            by_craft.setdefault(p.get("craft", "?"), []).append(p.get("name", "?"))
        crafts = [{"name": c, "people": ppl} for c, ppl in by_craft.items()]
        return {
            "count": j.get("number", len(people)),
            "crafts": crafts,
        }
