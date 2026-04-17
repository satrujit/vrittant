"""UPI monthly transaction statistics from NPCI.

NPCI publishes the official monthly UPI volume + value table at
``npci.org.in/what-we-do/upi/product-statistics``. The page is JS-rendered, so
we go through the ``r.jina.ai`` markdown proxy and parse the resulting table.

We surface the most-recent three months plus a derived per-day average for the
latest month — the most "headline-friendly" framing.
"""
from __future__ import annotations

import calendar
import re
from datetime import date

import httpx

from widgets_core import WidgetPlugin, register

PROXY = "https://r.jina.ai/https://www.npci.org.in/what-we-do/upi/product-statistics"

# Month rows in the table look like:
#   | January-2026 | 691 | 21,703.44 | 28,33,481.22 |
ROW_RE = re.compile(
    r"\|\s*([A-Z][a-z]+-\d{4})\s*\|\s*([\d,]+)\s*\|\s*([\d,.]+)\s*\|\s*([\d,.]+)\s*\|"
)

MONTHS_OR = {
    "January":   "ଜାନୁଆରୀ",   "February": "ଫେବୃଆରୀ", "March":  "ମାର୍ଚ୍ଚ",
    "April":     "ଏପ୍ରିଲ୍",     "May":      "ମେ",        "June":   "ଜୁନ୍",
    "July":      "ଜୁଲାଇ",      "August":   "ଅଗଷ୍ଟ",     "September": "ସେପ୍ଟେମ୍ବର",
    "October":   "ଅକ୍ଟୋବର",   "November": "ନଭେମ୍ବର",  "December": "ଡିସେମ୍ବର",
}
MONTH_NUM = {name: i for i, name in enumerate(calendar.month_name) if name}


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


@register
class UpiStatsWidget(WidgetPlugin):
    id = "upi_stats"
    category = "markets"
    template = "upi_stats.html"
    title_en = "UPI Transactions"
    title_or = "UPI କାରବାର"
    dedup_strategy = "deterministic"
    source_name = "NPCI"
    source_url = "https://www.npci.org.in/what-we-do/upi/product-statistics"
    timeout_seconds = 60

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(PROXY)
            r.raise_for_status()
            text = r.text

        rows: list[dict] = []
        for m in ROW_RE.finditer(text):
            label, banks, vol_mn, val_cr = m.group(1), m.group(2), m.group(3), m.group(4)
            month_name, year = label.split("-")
            month_num = MONTH_NUM.get(month_name)
            if not month_num:
                continue
            year_i = int(year)
            days = calendar.monthrange(year_i, month_num)[1]
            volume_mn = _to_float(vol_mn)
            value_cr = _to_float(val_cr)
            rows.append({
                "label_en":  label,
                "label_or":  f"{MONTHS_OR.get(month_name, month_name)} {year}",
                "banks":     int(banks.replace(",", "")),
                "volume_mn": volume_mn,                 # millions of txns/month
                "value_cr":  value_cr,                  # ₹ crore / month
                "value_lakh_cr": round(value_cr / 100000.0, 2),
                "daily_volume_mn": round(volume_mn / days, 1),
                "daily_value_cr":  round(value_cr / days, 0),
            })
            if len(rows) >= 3:
                break

        return {
            "as_of": date.today().isoformat(),
            "rows": rows,
        }
