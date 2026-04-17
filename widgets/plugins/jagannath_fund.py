"""Static call-to-action widget for the Shree Jagannath Temple donation fund."""
from __future__ import annotations

from widgets_core import WidgetPlugin, register


@register
class JagannathFundWidget(WidgetPlugin):
    id = "jagannath_fund"
    category = "spiritual"
    template = "jagannath_fund.html"
    title_en = "Donate to Shree Jagannath Temple"
    title_or = "ଶ୍ରୀ ଜଗନ୍ନାଥ ମନ୍ଦିର ଦାନ"
    dedup_strategy = "deterministic"
    source_name = "Shree Jagannath Temple Administration"
    source_url = "https://shreejagannatha.in/"

    async def fetch(self) -> dict:
        return {
            "donate_url": "https://shreejagannatha.in/online-donation/",
            "ack_url": "https://shreejagannatha.in/donation-acknowledgment/",
        }
