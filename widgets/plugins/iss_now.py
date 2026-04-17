"""ISS current position via Open Notify."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = "http://api.open-notify.org/iss-now.json"


@register
class IssNowWidget(WidgetPlugin):
    id = "iss_now"
    category = "science"
    template = "iss_now.html"
    title_en = "ISS — Current Position"
    title_or = "ISS ବର୍ତ୍ତମାନ ସ୍ଥାନ"
    dedup_strategy = "none"
    source_name = "Open Notify"
    source_url = "http://open-notify.org/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        pos = j.get("iss_position") or {}
        lat = float(pos.get("latitude", 0))
        lon = float(pos.get("longitude", 0))
        return {
            "lat": round(lat, 3),
            "lon": round(lon, 3),
            "lat_dir": "N" if lat >= 0 else "S",
            "lon_dir": "E" if lon >= 0 else "W",
        }
