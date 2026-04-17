"""Daily sudoku puzzle (easy/medium/hard rotation) via dosuku."""
from __future__ import annotations

from datetime import date

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://sudoku-api.vercel.app/api/dosuku"


@register
class SudokuPuzzleWidget(WidgetPlugin):
    id = "sudoku_puzzle"
    category = "games"
    template = "sudoku_puzzle.html"
    title_en = "Daily Sudoku"
    title_or = "ଆଜିର ସୁଡୋକୁ"
    dedup_strategy = "deterministic"
    source_name = "Dosuku"
    source_url = "https://sudoku-api.vercel.app/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        grid = (j.get("newboard", {}).get("grids") or [{}])[0]
        return {
            "value": grid.get("value") or [],
            "solution": grid.get("solution") or [],
            "difficulty": grid.get("difficulty") or "Medium",
            "date": date.today().isoformat(),
        }

    def dedup_key(self, payload: dict) -> str:
        return f"sudoku-{payload.get('date')}"
