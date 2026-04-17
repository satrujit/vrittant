"""IPL — recent results via TheSportsDB season feed (free, no key)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id=4460&s={season}"
_IST = timezone(timedelta(hours=5, minutes=30))


@register
class IplRecentWidget(WidgetPlugin):
    id = "ipl_recent"
    category = "sports"
    template = "ipl_recent.html"
    title_en = "IPL — Recent Results"
    title_or = "ଆଇପିଏଲ୍ — ସାମ୍ପ୍ରତିକ ଫଳାଫଳ"
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
        # Past matches with a recorded score
        past = [
            e for e in events
            if (e.get("dateEvent") or "") < today and e.get("intHomeScore") is not None
        ]
        past.sort(key=lambda e: e.get("dateEvent") or "", reverse=True)

        rows = []
        for e in past[:5]:
            rows.append({
                "home": e.get("strHomeTeam") or "",
                "away": e.get("strAwayTeam") or "",
                "home_score": e.get("intHomeScore"),
                "away_score": e.get("intAwayScore"),
                "date": e.get("dateEvent") or "",
                "venue": e.get("strVenue") or "",
            })
        return {"rows": rows}
