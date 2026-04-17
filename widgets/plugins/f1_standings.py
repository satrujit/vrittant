"""Formula 1 — current driver standings via Jolpica (Ergast API mirror)."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://api.jolpi.ca/ergast/f1/current/driverStandings.json"


@register
class F1StandingsWidget(WidgetPlugin):
    id = "f1_standings"
    category = "sports"
    template = "f1_standings.html"
    title_en = "F1 Driver Standings"
    title_or = "ଫର୍ମୁଲା ୧ — ଡ୍ରାଇଭର ସ୍ଥାନ"
    dedup_strategy = "none"
    source_name = "Jolpica F1 (Ergast)"
    source_url = "https://api.jolpi.ca/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        lists = (j.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists") or [])
        season = lists[0].get("season", "") if lists else ""
        rows = []
        for s in (lists[0].get("DriverStandings", []) if lists else [])[:8]:
            d = s.get("Driver", {})
            con = (s.get("Constructors") or [{}])[0]
            rows.append({
                "pos": s.get("position"),
                "name": f'{d.get("givenName", "")} {d.get("familyName", "")}'.strip(),
                "team": con.get("name", ""),
                "points": s.get("points"),
            })
        return {"season": season, "rows": rows}
