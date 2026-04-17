"""Commodities — gold, silver, crude oil futures via Yahoo Finance v8 chart API.

The v8 chart endpoint works without an API key or auth crumb. Each symbol's
``meta.regularMarketPrice`` is the latest traded price (USD); on weekends this
returns the previous close, so the widget never shows blanks.
"""
from __future__ import annotations

import asyncio

import httpx

from widgets_core import WidgetPlugin, register

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
FRANKFURTER = "https://api.frankfurter.dev/v1/latest?from=USD&to=INR"
GRAMS_PER_OZ = 31.1035

# (yahoo symbol, key, label_en, label_or, unit_for_inr)
SYMBOLS = [
    ("GC=F", "gold", "Gold (10g)", "ସୁନା (୧୦ ଗ୍ରାମ)", "per_10g"),
    ("SI=F", "silver", "Silver (1kg)", "ରୂପା (୧ କିଲୋ)", "per_kg"),
    ("CL=F", "wti", "WTI Crude (bbl)", "WTI ଅଶୋଧିତ ତୈଳ (ବ୍ୟାରେଲ)", "per_bbl"),
    ("BZ=F", "brent", "Brent Crude (bbl)", "Brent ତୈଳ (ବ୍ୟାରେଲ)", "per_bbl"),
]


async def _yahoo_price(client: httpx.AsyncClient, symbol: str) -> float | None:
    try:
        r = await client.get(
            YAHOO.format(symbol=symbol),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15.0,
        )
        r.raise_for_status()
        return r.json()["chart"]["result"][0]["meta"].get("regularMarketPrice")
    except Exception:
        return None


@register
class CommoditiesWidget(WidgetPlugin):
    id = "commodities"
    category = "markets"
    template = "commodities.html"
    title_en = "Gold, Silver & Oil"
    title_or = "ସୁନା, ରୂପା ଓ ତୈଳ"
    dedup_strategy = "none"
    source_name = "Yahoo Finance · ECB"
    source_url = "https://finance.yahoo.com/commodities"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Fetch USD→INR + all commodity prices in parallel
            usd_inr_task = client.get(FRANKFURTER, timeout=15.0)
            price_tasks = [_yahoo_price(client, s[0]) for s in SYMBOLS]
            results = await asyncio.gather(usd_inr_task, *price_tasks)

        usd_inr_resp = results[0]
        usd_inr = 0.0
        try:
            usd_inr_resp.raise_for_status()
            usd_inr = float(usd_inr_resp.json()["rates"]["INR"])
        except Exception:
            pass

        rows = []
        for (sym, key, label_en, label_or, unit), price in zip(SYMBOLS, results[1:]):
            if not price:
                continue
            row: dict = {
                "key": key,
                "label_or": label_or,
                "label_en": label_en,
                "usd": round(price, 2),
            }
            if unit == "per_10g" and usd_inr:
                row["inr"] = int(round(price * usd_inr / GRAMS_PER_OZ * 10))
            elif unit == "per_kg" and usd_inr:
                row["inr"] = int(round(price * usd_inr / GRAMS_PER_OZ * 1000))
            else:
                row["inr"] = None
            rows.append(row)

        return {
            "usd_inr": round(usd_inr, 2) if usd_inr else None,
            "rows": rows,
        }
