"""Metro weather — current temps for Indian metros via Open-Meteo batch."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

CITIES = [
    ("Delhi", "ଦିଲ୍ଲୀ", 28.6139, 77.2090),
    ("Mumbai", "ମୁମ୍ବାଇ", 19.0760, 72.8777),
    ("Bangalore", "ବେଙ୍ଗାଲୁରୁ", 12.9716, 77.5946),
    ("Chennai", "ଚେନ୍ନାଇ", 13.0827, 80.2707),
    ("Kolkata", "କଲିକତା", 22.5726, 88.3639),
    ("Hyderabad", "ହାଇଦ୍ରାବାଦ", 17.3850, 78.4867),
]

URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lats}&longitude={lons}"
    "&current=temperature_2m,weather_code"
    "&daily=temperature_2m_max,temperature_2m_min"
    "&forecast_days=1&timezone=Asia%2FKolkata"
)


@register
class MetroWeatherWidget(WidgetPlugin):
    id = "metro_weather"
    category = "weather"
    template = "metro_weather.html"
    title_en = "Metros — Weather Today"
    title_or = "ମୁଖ୍ୟ ସହର — ଆଜିର ପାଣିପାଗ"
    dedup_strategy = "none"
    source_name = "Open-Meteo"
    source_url = "https://open-meteo.com/"

    async def fetch(self) -> dict:
        lats = ",".join(f"{c[2]}" for c in CITIES)
        lons = ",".join(f"{c[3]}" for c in CITIES)
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL.format(lats=lats, lons=lons))
            r.raise_for_status()
            data = r.json()

        # Open-Meteo returns a list when multiple coords are given
        if isinstance(data, dict):
            data = [data]

        rows = []
        for city, (en, orx, _, _) in zip(data, ((c[0], c[1], c[2], c[3]) for c in CITIES)):
            cur = city.get("current", {})
            daily = city.get("daily", {})
            tmax = (daily.get("temperature_2m_max") or [None])[0]
            tmin = (daily.get("temperature_2m_min") or [None])[0]
            rows.append({
                "name_en": en,
                "name_or": orx,
                "temp": cur.get("temperature_2m"),
                "tmax": tmax,
                "tmin": tmin,
            })
        return {"rows": rows}
