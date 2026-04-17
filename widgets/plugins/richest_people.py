"""World's richest — top 10 from Forbes' annual Billionaires list.

Forbes publishes the ranking for each year at
``forbes.com/billionaires/`` and ships the data to the page via an internal
JSON endpoint (``/forbesapi/person/billionaires/<year>/...``). We read that
feed directly and translate English names to Odia via Sarvam.
"""
from __future__ import annotations

from datetime import date

import httpx

from widgets_core import WidgetPlugin, register

# The page forbes.com/billionaires/ loads data from this year-keyed JSON
# feed. We attempt the current year first, then fall back to previous years
# if Forbes has not yet cut the ranking for this year.
BASE = (
    "https://www.forbes.com/forbesapi/person/billionaires/{year}/position/true.json"
    "?fields=rank,personName,finalWorth,source,countryOfCitizenship&limit=10"
)


@register
class RichestPeopleWidget(WidgetPlugin):
    id = "richest_people"
    category = "markets"
    template = "richest_people.html"
    title_en = "World's Richest"
    title_or = "ବିଶ୍ୱର ସବୁଠାରୁ ଧନୀ"
    dedup_strategy = "deterministic"
    source_name = "Forbes Billionaires"
    source_url = "https://www.forbes.com/billionaires/"
    # Proper-noun transliteration via Sarvam is unreliable; show
    # English names + company labels as-is. Globally recognised.
    timeout_seconds = 60

    async def fetch(self) -> dict:
        today = date.today()
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.forbes.com/billionaires/",
        }
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
            data = None
            year_used = today.year
            for year in (today.year, today.year - 1, today.year - 2):
                r = await client.get(BASE.format(year=year))
                if r.status_code != 200:
                    continue
                j = r.json() or {}
                lst = (j.get("personList") or {}).get("personsLists") or []
                if lst:
                    data = lst
                    year_used = year
                    break
            if data is None:
                return {"snapshot": "Forbes", "rows": []}

        rows = []
        for p in data[:10]:
            worth_m = p.get("finalWorth") or 0  # USD millions
            worth_b = round(float(worth_m) / 1000.0, 1)
            name = p.get("personName") or ""
            src = p.get("source") or ""
            rows.append({
                "rank": p.get("rank"),
                "name": name,
                "name_or": name,   # overwritten by translator
                "src": src,
                "src_or": src,     # overwritten by translator
                "wealth_usd_b": worth_b,
            })
        return {"snapshot": f"Forbes {year_used}", "rows": rows}
