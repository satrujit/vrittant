"""Crypto prices in INR — CoinGecko (free, no key)."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum,solana,binancecoin,ripple"
    "&vs_currencies=inr&include_24hr_change=true"
)

COINS = [
    ("bitcoin", "Bitcoin", "ବିଟ୍‌କଏନ୍"),
    ("ethereum", "Ethereum", "ଇଥେରିୟମ୍"),
    ("solana", "Solana", "ସୋଲାନା"),
    ("binancecoin", "BNB", "BNB"),
    ("ripple", "XRP", "XRP"),
]


@register
class CryptoPricesWidget(WidgetPlugin):
    id = "crypto_prices"
    category = "markets"
    template = "crypto_prices.html"
    title_en = "Crypto Prices (INR)"
    title_or = "କ୍ରିପ୍ଟୋ ମୂଲ୍ୟ (INR)"
    dedup_strategy = "none"
    source_name = "CoinGecko"
    source_url = "https://www.coingecko.com/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        rows = []
        for cid, name_en, name_or in COINS:
            d = j.get(cid) or {}
            price = d.get("inr")
            chg = d.get("inr_24h_change")
            if price is None:
                continue
            rows.append({
                "name_en": name_en,
                "name_or": name_or,
                "price": round(price, 2),
                "change_pct": round(chg, 2) if chg is not None else None,
            })
        return {"rows": rows}
