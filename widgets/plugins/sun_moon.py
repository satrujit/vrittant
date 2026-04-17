"""Sunrise/sunset + moon phase for Bhubaneswar — Open-Meteo (free, no key)."""
from __future__ import annotations

import math
from datetime import date

import httpx

from widgets_core import WidgetPlugin, register

LAT, LON = 20.2961, 85.8245
URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&daily=sunrise,sunset,daylight_duration"
    "&forecast_days=1&timezone=Asia%2FKolkata"
)

# Reference new moon: 2000-01-06 18:14 UTC; synodic month ≈ 29.5305882 days
SYNODIC_MONTH = 29.5305882
NEW_MOON_REF_JD = 2451550.1


def _moon_phase_today() -> tuple[float, str, str]:
    """Return (illumination 0-1, phase name English, phase name Odia)."""
    today = date.today().toordinal()
    # Convert to Julian Day Number
    jd = today + 1721424.5
    age = ((jd - NEW_MOON_REF_JD) % SYNODIC_MONTH + SYNODIC_MONTH) % SYNODIC_MONTH
    # Illumination as fraction (0 = new, 1 = full)
    illum = (1 - math.cos(2 * math.pi * age / SYNODIC_MONTH)) / 2

    if age < 1.84566:
        en, orx = "New Moon", "ଅମାବାସ୍ୟା"
    elif age < 5.53699:
        en, orx = "Waxing Crescent", "ଶୁକ୍ଳ ପକ୍ଷ ଚନ୍ଦ୍ର"
    elif age < 9.22831:
        en, orx = "First Quarter", "ଅଷ୍ଟମୀ"
    elif age < 12.91963:
        en, orx = "Waxing Gibbous", "ଶୁକ୍ଳ ଗିବସ୍"
    elif age < 16.61096:
        en, orx = "Full Moon", "ପୂର୍ଣ୍ଣିମା"
    elif age < 20.30228:
        en, orx = "Waning Gibbous", "କୃଷ୍ଣ ଗିବସ୍"
    elif age < 23.99361:
        en, orx = "Last Quarter", "କୃଷ୍ଣ ଅଷ୍ଟମୀ"
    elif age < 27.68493:
        en, orx = "Waning Crescent", "କୃଷ୍ଣ ପକ୍ଷ ଚନ୍ଦ୍ର"
    else:
        en, orx = "New Moon", "ଅମାବାସ୍ୟା"
    return round(illum, 2), en, orx


def _hhmm(iso_ts: str) -> str:
    """Take '2026-04-17T05:42' → '05:42'."""
    if not iso_ts or "T" not in iso_ts:
        return iso_ts or ""
    return iso_ts.split("T", 1)[1][:5]


@register
class SunMoonWidget(WidgetPlugin):
    id = "sun_moon"
    category = "spiritual"
    template = "sun_moon.html"
    title_en = "Sun & Moon — Bhubaneswar"
    title_or = "ସୂର୍ଯ୍ୟ ଓ ଚନ୍ଦ୍ର"
    dedup_strategy = "none"
    source_name = "Open-Meteo"
    source_url = "https://open-meteo.com/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            d = r.json().get("daily", {})

        sunrise = (d.get("sunrise") or [""])[0]
        sunset = (d.get("sunset") or [""])[0]
        daylight_s = (d.get("daylight_duration") or [0])[0] or 0
        h, m = divmod(int(daylight_s) // 60, 60)

        illum, phase_en, phase_or = _moon_phase_today()
        return {
            "sunrise": _hhmm(sunrise),
            "sunset": _hhmm(sunset),
            "daylight": f"{h}h {m}m",
            "moon_illum_pct": int(round(illum * 100)),
            "moon_phase_en": phase_en,
            "moon_phase_or": phase_or,
        }
