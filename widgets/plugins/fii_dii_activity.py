"""FII/DII trading activity in India — daily provisional data from NSE."""
from __future__ import annotations

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://www.nseindia.com/api/fiidiiTradeReact"


@register
class FiiDiiActivityWidget(WidgetPlugin):
    id = "fii_dii_activity"
    category = "markets"
    template = "fii_dii_activity.html"
    title_en = "FII / DII Activity"
    title_or = "FII / DII କାରବାର"
    dedup_strategy = "none"
    source_name = "NSE India"
    source_url = "https://www.nseindia.com/reports/fii-dii"

    async def fetch(self) -> dict:
        # NSE requires a UA + a prior cookie set on its homepage; the API
        # returns 401 without it. We follow the standard cookie-warm pattern.
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nseindia.com/reports/fii-dii",
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            # Warm cookies
            try:
                await client.get("https://www.nseindia.com")
            except Exception:
                pass
            r = await client.get(URL)
            r.raise_for_status()
            entries = r.json() or []

        rows = []
        date_str = ""
        for e in entries:
            cat = e.get("category", "")
            date_str = e.get("date", date_str)
            try:
                buy = float(e.get("buyValue") or 0)
                sell = float(e.get("sellValue") or 0)
                net = float(e.get("netValue") or 0)
            except ValueError:
                continue
            label_or = "FII / FPI" if "FII" in cat or "FPI" in cat else "DII"
            rows.append({
                "label_en": cat,
                "label_or": label_or,
                "buy": buy,
                "sell": sell,
                "net": net,
            })
        return {"date": date_str, "rows": rows}
