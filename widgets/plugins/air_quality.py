"""Air quality — Bhubaneswar via Open-Meteo air-quality API (free, no key)."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

LAT, LON = 20.2961, 85.8245
URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality"
    f"?latitude={LAT}&longitude={LON}"
    "&current=pm10,pm2_5,carbon_monoxide,ozone,nitrogen_dioxide,sulphur_dioxide,european_aqi"
    "&timezone=Asia%2FKolkata"
)


def _aqi_band(aqi: float | None) -> tuple[str, str]:
    """Return (English label, Odia label) for a European AQI value."""
    if aqi is None:
        return ("—", "—")
    if aqi <= 20:
        return ("Good", "ଭଲ")
    if aqi <= 40:
        return ("Fair", "ଠିକ୍")
    if aqi <= 60:
        return ("Moderate", "ମଧ୍ୟମ")
    if aqi <= 80:
        return ("Poor", "ଖରାପ")
    if aqi <= 100:
        return ("Very poor", "ଅତି ଖରାପ")
    return ("Extremely poor", "ଅତ୍ୟନ୍ତ ଖରାପ")


@register
class AirQualityWidget(WidgetPlugin):
    id = "air_quality"
    category = "weather"
    template = "air_quality.html"
    title_en = "Air Quality — Bhubaneswar"
    title_or = "ବାୟୁ ଗୁଣବତ୍ତା — ଭୁବନେଶ୍ୱର"
    dedup_strategy = "none"
    source_name = "Open-Meteo Air Quality"
    source_url = "https://open-meteo.com/en/docs/air-quality-api"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            cur = r.json().get("current", {})

        aqi = cur.get("european_aqi")
        label_en, label_or = _aqi_band(aqi)
        return {
            "aqi": aqi,
            "band_en": label_en,
            "band_or": label_or,
            "pm2_5": cur.get("pm2_5"),
            "pm10": cur.get("pm10"),
            "ozone": cur.get("ozone"),
            "no2": cur.get("nitrogen_dioxide"),
            "so2": cur.get("sulphur_dioxide"),
            "co": cur.get("carbon_monoxide"),
        }
