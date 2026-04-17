"""Days/hours until next New Year (Gregorian)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from widgets_core import WidgetPlugin, register

_IST = timezone(timedelta(hours=5, minutes=30))


@register
class NewYearCountdownWidget(WidgetPlugin):
    id = "new_year_countdown"
    category = "knowledge"
    template = "new_year_countdown.html"
    title_en = "Time Until New Year"
    title_or = "ନୂତନ ବର୍ଷକୁ ସମୟ"
    dedup_strategy = "deterministic"
    source_name = "Local clock"
    source_url = ""

    async def fetch(self) -> dict:
        now = datetime.now(_IST)
        next_year = now.year + 1
        target = datetime(next_year, 1, 1, 0, 0, 0, tzinfo=_IST)
        delta = target - now
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return {
            "next_year": next_year,
            "days": days,
            "hours": hours,
            "minutes": minutes,
        }
