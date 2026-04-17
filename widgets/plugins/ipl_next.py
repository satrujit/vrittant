"""IPL — upcoming fixtures via TheSportsDB season feed (free, no key)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from widgets_core import WidgetPlugin, register

# IPL league = 4460 on TheSportsDB. The eventsnextleague/eventspastleague
# endpoints return wrong (soccer) data on the free tier for this league, so
# we pull the whole season feed and filter client-side.
URL = "https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id=4460&s={season}"
_IST = timezone(timedelta(hours=5, minutes=30))


@register
class IplNextWidget(WidgetPlugin):
    id = "ipl_next"
    category = "sports"
    template = "ipl_next.html"
    title_en = "IPL — Next Matches"
    title_or = "ଆଇପିଏଲ୍ — ପରବର୍ତ୍ତୀ ମ୍ୟାଚ୍"
    dedup_strategy = "none"
    translate_fields = ["rows.*.home", "rows.*.away", "rows.*.venue"]
    source_name = "TheSportsDB"
    source_url = "https://www.thesportsdb.com/"

    async def fetch(self) -> dict:
        season = str(datetime.now(_IST).year)
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL.format(season=season))
            r.raise_for_status()
            j = r.json()

        today = datetime.now(_IST).strftime("%Y-%m-%d")
        events = j.get("events") or []
        upcoming = [e for e in events if (e.get("dateEvent") or "") >= today]
        upcoming.sort(key=lambda e: (e.get("dateEvent") or "", e.get("strTime") or ""))

        rows = []
        for e in upcoming[:5]:
            rows.append({
                "home": e.get("strHomeTeam") or "",
                "away": e.get("strAwayTeam") or "",
                "date": e.get("dateEvent") or "",
                "time": (e.get("strTime") or "")[:5],
                "venue": e.get("strVenue") or "",
            })
        return {"rows": rows}
