"""Daily chess puzzle from Lichess — board image + a rotating play tip."""
from __future__ import annotations

from datetime import date

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://lichess.org/api/puzzle/daily"

# Curated rotation of one practical chess principle per day (in Odia)
TIPS_OR = [
    "ଖୋଲିବା ସମୟରେ କେନ୍ଦ୍ର ଦୁର୍ଗ ଦଖଲ କରନ୍ତୁ — d4, e4, d5, e5 ବୁଦ୍ଧିମାନ୍ ଚାଲ।",
    "ନାଇଟ୍‌କୁ କିନାରଠାରୁ ଦୂରେ ରଖନ୍ତୁ — \"Knights on the rim are dim.\"",
    "ଖୋଲିବା ଶେଷରେ ରାଜାକୁ କ୍ୟାସଲ୍ କରି ସୁରକ୍ଷିତ କରନ୍ତୁ।",
    "ପ୍ରତ୍ୟେକ ଚାଲରେ ବିପକ୍ଷର ବିପଦ ଯାଞ୍ଚ କରନ୍ତୁ — checks, captures, threats।",
    "ସମାନ ପିସ୍ ଦୁଇଥର ଚଲାଇବାକୁ ଏଡାନ୍ତୁ ଯଦି ଅନ୍ୟ ପିସ୍ ଅବିକଶିତ ଅଛନ୍ତି।",
    "ଶେଷ ଖେଳରେ ରାଜା ଏକ ଶକ୍ତିଶାଳୀ ପିସ୍ — ତାକୁ କେନ୍ଦ୍ରକୁ ଆଣନ୍ତୁ।",
    "ଦୁଇଟି ବିଶପ୍ ଖୋଲା ବୋର୍ଡରେ ଦୁଇଟି ନାଇଟ୍ ଠାରୁ ଶକ୍ତିଶାଳୀ।",
    "ପାସ୍ଡ୍ ପୋନ୍‌ର ସ୍ଥାନ ସର୍ବଶ୍ରେଷ୍ଠ — ସେମାନେ ଶେଷ ଖେଳରେ ବିଜୟ ଆଣିଥାଏ।",
    "Rook କୁ ଖୋଲା ଫାଇଲ୍‌ ଉପରେ ସ୍ଥାପନ କରନ୍ତୁ ଅଧିକତମ କାର୍ଯ୍ୟକ୍ଷମତା ପାଇଁ।",
    "ସମୟ ସମ୍ବନ୍ଧୀୟ ଚାପରେ ସରଳ ଚାଲ କରନ୍ତୁ — ଜଟିଳ ଚାଲ ଭୁଲ୍ ତିଆରି କରେ।",
    "ବିପକ୍ଷର ଯୋଜନା କ'ଣ — ତାହା ବୁଝି ତାହାକୁ ବାଧା ଦେବା ଗୁରୁତ୍ୱପୂର୍ଣ୍ଣ।",
    "ମେଟେରିଆଲ୍ ଗଣିବା ପୂର୍ବରୁ ଅବସ୍ଥାନର ଗୁଣବତ୍ତା ଯାଞ୍ଚ କରନ୍ତୁ।",
    "ପ୍ରତିଟି ଚାଲ ଏକ ଯୋଜନା ଅନୁସରଣ କରୁ — ଯୋଜନା ବିନା ଚାଲ ଦୁର୍ବଳ।",
    "ବିପଦରେ ପଡ଼ିଲେ ବ୍ୟବସାୟ କରି ବାହାରନ୍ତୁ — exchange ସରଳୀକରଣ ଆଣେ।",
]


@register
class ChessPuzzleWidget(WidgetPlugin):
    id = "chess_puzzle"
    category = "games"
    template = "chess_puzzle.html"
    title_en = "Daily Chess Puzzle & Tip"
    title_or = "ଆଜିର ଚେସ୍ ପଜଲ୍ ଓ ଟିପ୍ସ"
    dedup_strategy = "deterministic"
    source_name = "Lichess"
    source_url = "https://lichess.org/training"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        puzzle = j.get("puzzle", {})
        game = j.get("game", {})
        pid = puzzle.get("id", "")
        # Lichess GIF service renders the board for any puzzle by FEN — we
        # use the simpler thumbnail endpoint that takes the puzzle id.
        board_img = f"https://lichess1.org/training/export/gif/thumbnail/{pid}.gif" if pid else ""
        tip = TIPS_OR[date.today().toordinal() % len(TIPS_OR)]
        return {
            "puzzle_id": pid,
            "rating": puzzle.get("rating"),
            "themes": puzzle.get("themes") or [],
            "url": f"https://lichess.org/training/{pid}" if pid else "",
            "board_img": board_img,
            "players": [p.get("name", "?") for p in (game.get("players") or [])],
            "tip_or": tip,
        }
