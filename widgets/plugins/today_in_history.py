"""Today in history — Muffinlabs free API (no key)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://history.muffinlabs.com/date/{m}/{d}"
_IST = timezone(timedelta(hours=5, minutes=30))


@register
class TodayInHistoryWidget(WidgetPlugin):
    id = "today_in_history"
    category = "knowledge"
    template = "today_in_history.html"
    title_en = "Today in History"
    title_or = "ଆଜିର ଇତିହାସରେ"
    dedup_strategy = "deterministic"  # same date → same content (intentional)
    timeout_seconds = 90  # ~50 events translated in parallel batches
    translate_fields = ["events.*.text"]
    source_name = "Muffinlabs / Wikipedia"
    source_url = "https://history.muffinlabs.com/"

    async def fetch(self) -> dict:
        now = datetime.now(_IST)
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(URL.format(m=now.month, d=now.day))
            r.raise_for_status()
            j = r.json()

        # API returns up to ~50 events — keep all of them.
        events = []
        for e in (j.get("data", {}).get("Events", []) or []):
            events.append({
                "year": e.get("year"),
                "text": e.get("text", "").strip(),
            })
        return {
            "month": now.month,
            "day": now.day,
            "label": now.strftime("%d %B"),
            "events": events,
        }

    def dedup_key(self, payload: dict) -> str:
        return f"{payload['month']:02d}-{payload['day']:02d}"
