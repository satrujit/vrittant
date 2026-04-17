"""Indian stock indices — Sensex, Nifty 50, Bank Nifty via Yahoo Finance."""
from __future__ import annotations

import asyncio

import httpx

from widgets_core import WidgetPlugin, register

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"

# (yahoo symbol, label_en, label_or)
INDICES = [
    ("^BSESN", "BSE Sensex", "ସେନସେକ୍ସ"),
    ("^NSEI", "Nifty 50", "ନିଫ୍ଟି ୫୦"),
    ("^NSEBANK", "Bank Nifty", "ବ୍ୟାଙ୍କ ନିଫ୍ଟି"),
    ("^CNXIT", "Nifty IT", "ନିଫ୍ଟି IT"),
]


async def _quote(client: httpx.AsyncClient, symbol: str) -> dict | None:
    try:
        r = await client.get(
            YAHOO.format(symbol=symbol),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15.0,
        )
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None:
            return None
        change = (price - prev) if prev else 0
        pct = (change / prev * 100) if prev else 0
        return {"price": price, "change": change, "pct": pct}
    except Exception:
        return None


@register
class StockIndicesWidget(WidgetPlugin):
    id = "stock_indices"
    category = "markets"
    template = "stock_indices.html"
    title_en = "Indian Stock Indices"
    title_or = "ଭାରତୀୟ ଶେୟାର ବଜାର"
    dedup_strategy = "none"
    source_name = "Yahoo Finance"
    source_url = "https://finance.yahoo.com/world-indices"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            quotes = await asyncio.gather(*(_quote(client, s[0]) for s in INDICES))

        rows = []
        for (sym, en, orx), q in zip(INDICES, quotes):
            if not q:
                continue
            rows.append({
                "label_en": en,
                "label_or": orx,
                "price": round(q["price"], 2),
                "change": round(q["change"], 2),
                "pct": round(q["pct"], 2),
            })
        return {"rows": rows}
