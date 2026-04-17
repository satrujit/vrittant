"""Odisha temperatures — hottest-to-coldest district ranking for today.

Uses Open-Meteo's batch mode (comma-separated lat/lon) to fetch current
temperatures for a curated list of Odisha cities in one request.
"""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

# (English name, Odia name, latitude, longitude)
CITIES: list[tuple[str, str, float, float]] = [
    ("Bhubaneswar", "ଭୁବନେଶ୍ୱର", 20.2961, 85.8245),
    ("Cuttack", "କଟକ", 20.4625, 85.8830),
    ("Puri", "ପୁରୀ", 19.8135, 85.8312),
    ("Berhampur", "ବ୍ରହ୍ମପୁର", 19.3149, 84.7941),
    ("Sambalpur", "ସମ୍ବଲପୁର", 21.4669, 83.9756),
    ("Rourkela", "ରାଉରକେଲା", 22.2604, 84.8536),
    ("Balasore", "ବାଲେଶ୍ୱର", 21.4942, 86.9335),
    ("Angul", "ଅନୁଗୋଳ", 20.8398, 85.1014),
    ("Jharsuguda", "ଝାରସୁଗୁଡା", 21.8554, 84.0062),
    ("Koraput", "କୋରାପୁଟ", 18.8137, 82.7140),
    ("Bhawanipatna", "ଭବାନୀପାଟଣା", 19.9075, 83.1641),
    ("Baripada", "ବାରିପଦା", 21.9347, 86.7204),
    ("Phulbani", "ଫୁଲବାଣୀ", 20.4779, 84.2336),
    ("Talcher", "ତାଳଚେର", 20.9501, 85.2331),
    ("Sundargarh", "ସୁନ୍ଦରଗଡ", 22.1167, 84.0333),
]


@register
class OdishaTempsWidget(WidgetPlugin):
    id = "odisha_temps"
    category = "weather"
    template = "odisha_temps.html"
    title_en = "Odisha — Hottest to Coldest"
    title_or = "ଓଡ଼ିଶା — ସର୍ବାଧିକ ଠାରୁ ସର୍ବନିମ୍ନ ତାପମାତ୍ରା"
    dedup_strategy = "none"
    source_name = "Open-Meteo"
    source_url = "https://open-meteo.com/"

    async def fetch(self) -> dict:
        lats = ",".join(f"{c[2]:.4f}" for c in CITIES)
        lons = ",".join(f"{c[3]:.4f}" for c in CITIES)
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lats}&longitude={lons}"
            "&current=temperature_2m,relative_humidity_2m"
            "&daily=temperature_2m_max,temperature_2m_min"
            "&forecast_days=1&timezone=Asia%2FKolkata"
        )
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            results = r.json()

        # Open-Meteo returns either a list (one entry per city) or a single dict
        if not isinstance(results, list):
            results = [results]

        rows: list[dict] = []
        for (name_en, name_or, _lat, _lon), loc in zip(CITIES, results):
            cur = loc.get("current") or {}
            daily = loc.get("daily") or {}
            tmax = (daily.get("temperature_2m_max") or [None])[0]
            tmin = (daily.get("temperature_2m_min") or [None])[0]
            t_now = cur.get("temperature_2m")
            if t_now is None and tmax is None:
                continue
            rows.append({
                "name_en": name_en,
                "name_or": name_or,
                "now": t_now,
                "max": tmax,
                "min": tmin,
            })

        # Sort by today's maximum temperature, descending.
        rows.sort(key=lambda r: (r["max"] if r["max"] is not None else -1e9), reverse=True)
        return {"cities": rows}
