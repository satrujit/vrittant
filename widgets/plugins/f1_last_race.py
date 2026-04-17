"""Formula 1 — last race results via Jolpica (Ergast API mirror)."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://api.jolpi.ca/ergast/f1/current/last/results.json"


@register
class F1LastRaceWidget(WidgetPlugin):
    id = "f1_last_race"
    category = "sports"
    template = "f1_last_race.html"
    title_en = "F1 — Last Race Results"
    title_or = "ଫର୍ମୁଲା ୧ — ଗତ ରେସ୍ ଫଳାଫଳ"
    dedup_strategy = "none"
    source_name = "Jolpica F1 (Ergast)"
    source_url = "https://api.jolpi.ca/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        races = (j.get("MRData", {}).get("RaceTable", {}).get("Races") or [])
        if not races:
            return {"name": "", "circuit": "", "date": "", "rows": []}
        race = races[0]
        rows = []
        for res in (race.get("Results") or [])[:5]:
            d = res.get("Driver", {})
            con = res.get("Constructor", {})
            rows.append({
                "pos": res.get("position"),
                "name": f'{d.get("givenName", "")} {d.get("familyName", "")}'.strip(),
                "team": con.get("name", ""),
                "time": (res.get("Time") or {}).get("time") or res.get("status") or "",
            })
        return {
            "name": race.get("raceName", ""),
            "circuit": (race.get("Circuit") or {}).get("circuitName", ""),
            "date": race.get("date", ""),
            "rows": rows,
        }
