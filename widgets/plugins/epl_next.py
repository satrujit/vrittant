"""English Premier League — upcoming fixtures via TheSportsDB."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

# EPL league ID on TheSportsDB
URL = "https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id=4328"


@register
class EplNextWidget(WidgetPlugin):
    id = "epl_next"
    category = "sports"
    template = "epl_next.html"
    title_en = "Premier League — Next Matches"
    title_or = "ପ୍ରିମିୟର ଲିଗ୍ — ପରବର୍ତ୍ତୀ ମ୍ୟାଚ୍"
    dedup_strategy = "none"
    translate_fields = ["rows.*.home", "rows.*.away", "rows.*.venue"]
    source_name = "TheSportsDB"
    source_url = "https://www.thesportsdb.com/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        rows = []
        for e in (j.get("events") or [])[:5]:
            rows.append({
                "home": e.get("strHomeTeam") or "",
                "away": e.get("strAwayTeam") or "",
                "date": e.get("dateEvent") or "",
                "time": (e.get("strTime") or "")[:5],
                "venue": e.get("strVenue") or "",
            })
        return {"rows": rows}
