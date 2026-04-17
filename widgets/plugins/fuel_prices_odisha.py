"""Daily petrol & diesel prices in Bhubaneswar.

GoodReturns publishes Indian retail fuel prices daily; we read them through the
free Jina reader proxy (r.jina.ai) which converts the page to clean markdown.
Per-day fetch only — rate-limited by upstream so we keep the call count low.
"""
from __future__ import annotations

import re
from datetime import date

import httpx

from widgets_core import WidgetPlugin, register

PROXY = "https://r.jina.ai/https://www.goodreturns.in/{fuel}-price-in-bhubaneswar.html"
PRICE_RE = re.compile(r"is at ₹\*\*([0-9]+\.[0-9]+)\*\*")


async def _price(client: httpx.AsyncClient, fuel: str) -> float | None:
    try:
        r = await client.get(PROXY.format(fuel=fuel), timeout=20.0)
        r.raise_for_status()
        m = PRICE_RE.search(r.text)
        return float(m.group(1)) if m else None
    except Exception:
        return None


@register
class FuelPricesOdishaWidget(WidgetPlugin):
    id = "fuel_prices_odisha"
    category = "markets"
    template = "fuel_prices_odisha.html"
    title_en = "Fuel Prices — Bhubaneswar"
    title_or = "ଇନ୍ଧନ ମୂଲ୍ୟ — ଭୁବନେଶ୍ୱର"
    dedup_strategy = "none"
    source_name = "GoodReturns"
    source_url = "https://www.goodreturns.in/petrol-price-in-bhubaneswar.html"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            petrol = await _price(client, "petrol")
            diesel = await _price(client, "diesel")

        rows = []
        if petrol is not None:
            rows.append({"label_en": "Petrol", "label_or": "ପେଟ୍ରୋଲ୍", "price": petrol, "unit": "/L"})
        if diesel is not None:
            rows.append({"label_en": "Diesel", "label_or": "ଡିଜେଲ୍", "price": diesel, "unit": "/L"})

        return {"date": date.today().isoformat(), "rows": rows}
