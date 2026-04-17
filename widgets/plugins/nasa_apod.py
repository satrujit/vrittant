"""NASA Astronomy Picture of the Day — api.nasa.gov DEMO_KEY."""
from __future__ import annotations

import os

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://api.nasa.gov/planetary/apod"


@register
class NasaApodWidget(WidgetPlugin):
    id = "nasa_apod"
    category = "science"
    template = "nasa_apod.html"
    title_en = "NASA — Picture of the Day"
    title_or = "ନାସା — ଆଜିର ଚିତ୍ର"
    dedup_strategy = "deterministic"
    translate_fields = ["title", "explanation"]
    source_name = "NASA APOD"
    source_url = "https://apod.nasa.gov/apod/"

    async def fetch(self) -> dict:
        api_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL, params={"api_key": api_key})
            r.raise_for_status()
            j = r.json()

        # APOD can be image or video; pick a renderable URL
        img = j.get("url") if j.get("media_type") == "image" else j.get("thumbnail_url") or ""
        explanation = (j.get("explanation") or "").strip()
        # Trim to keep card compact
        if len(explanation) > 280:
            explanation = explanation[:277].rstrip() + "…"
        return {
            "date": j.get("date"),
            "title": j.get("title") or "",
            "image_url": img,
            "media_type": j.get("media_type"),
            "explanation": explanation,
            "copyright": (j.get("copyright") or "").strip(),
        }
