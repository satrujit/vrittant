"""Currency rates vs INR — Frankfurter (ECB rates, free, no key)."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://api.frankfurter.dev/v1/latest?from=INR&to=USD,EUR,GBP,JPY,AUD,SGD,AED"


@register
class CurrencyRatesWidget(WidgetPlugin):
    id = "currency_rates"
    category = "markets"
    template = "currency_rates.html"
    title_en = "Currency vs ₹"
    title_or = "ମୁଦ୍ରା ଦର"
    dedup_strategy = "none"
    source_name = "Frankfurter (ECB)"
    source_url = "https://www.frankfurter.app/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        # Frankfurter returns "1 INR = X foreign". Invert to get "1 foreign = N INR".
        rates_in_inr: list[dict] = []
        for code, per_inr in (j.get("rates") or {}).items():
            if per_inr:
                rates_in_inr.append({"code": code, "inr": round(1.0 / per_inr, 2)})
        rates_in_inr.sort(key=lambda x: x["code"])

        return {"date": j.get("date"), "rates": rates_in_inr}
