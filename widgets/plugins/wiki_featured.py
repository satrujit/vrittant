"""Wikipedia featured article of the day."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://en.wikipedia.org/api/rest_v1/feed/featured/{y}/{m:02d}/{d:02d}"
_IST = timezone(timedelta(hours=5, minutes=30))


@register
class WikiFeaturedWidget(WidgetPlugin):
    id = "wiki_featured"
    category = "knowledge"
    template = "wiki_featured.html"
    title_en = "Featured Article"
    title_or = "ବିଶେଷ ଲେଖା"
    dedup_strategy = "deterministic"
    timeout_seconds = 45
    translate_fields = ["extract"]
    source_name = "Wikimedia"
    source_url = "https://en.wikipedia.org/wiki/Wikipedia:Today%27s_featured_article"

    async def fetch(self) -> dict:
        now = datetime.now(_IST)
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Vrittant/1.0 (https://vrittant.in; contact@vrittant.in)",
                "Accept": "application/json",
            },
        ) as client:
            r = await client.get(URL.format(y=now.year, m=now.month, d=now.day))
            r.raise_for_status()
            j = r.json()

        tfa = j.get("tfa") or {}
        extract = (tfa.get("extract") or "").strip()
        # Keep extract punchy — first 2 sentences
        if extract:
            sentences = extract.split(". ")
            extract = ". ".join(sentences[:2]).rstrip(".") + "."
        return {
            "title": tfa.get("titles", {}).get("normalized") or tfa.get("title", ""),
            "description": tfa.get("description", ""),
            "extract": extract,
            "url": (tfa.get("content_urls", {}).get("desktop") or {}).get("page") or "",
            "image": (tfa.get("thumbnail") or {}).get("source") or "",
        }

    def dedup_key(self, payload: dict) -> str:
        return f"wiki-featured-{payload.get('title', '')}"
