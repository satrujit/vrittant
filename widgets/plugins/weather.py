"""Weather widget — Bhubaneswar 3-day forecast via Open-Meteo (free, no key)."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

# Bhubaneswar coordinates (default home edition city)
LAT, LON = 20.2961, 85.8245
URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&current=temperature_2m,relative_humidity_2m,weather_code"
    "&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum"
    "&forecast_days=3&timezone=Asia%2FKolkata"
)

# WMO weather code → short label (English)
CODE_LABEL = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Foggy",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Showers", 81: "Heavy showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunder + hail", 99: "Severe thunder",
}


@register
class WeatherWidget(WidgetPlugin):
    id = "weather"
    category = "weather"
    template = "weather.html"
    title_en = "Weather — Bhubaneswar"
    title_or = "ପାଣିପାଗ — ଭୁବନେଶ୍ୱର"
    dedup_strategy = "none"
    source_name = "Open-Meteo"
    source_url = "https://open-meteo.com/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(URL)
            r.raise_for_status()
            d = r.json()

        cur = d.get("current", {})
        daily = d.get("daily", {})
        days = []
        for i, date in enumerate(daily.get("time", [])):
            days.append({
                "date": date,
                "max_c": daily["temperature_2m_max"][i],
                "min_c": daily["temperature_2m_min"][i],
                "label": CODE_LABEL.get(daily["weather_code"][i], "—"),
                "precip_mm": daily["precipitation_sum"][i],
            })
        return {
            "city": "Bhubaneswar",
            "current": {
                "temp_c": cur.get("temperature_2m"),
                "humidity": cur.get("relative_humidity_2m"),
                "label": CODE_LABEL.get(cur.get("weather_code"), "—"),
            },
            "days": days,
        }
