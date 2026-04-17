"""Trivia question of the day from Open Trivia DB."""
from __future__ import annotations

import html as _html
import random

import httpx

from widgets_core import WidgetPlugin, register

URL = "https://opentdb.com/api.php?amount=1&type=multiple"


@register
class TriviaQuestionWidget(WidgetPlugin):
    id = "trivia_question"
    category = "games"
    template = "trivia_question.html"
    title_en = "Trivia Question"
    title_or = "ଆଜିର ସାଧାରଣ ଜ୍ଞାନ ପ୍ରଶ୍ନ"
    dedup_strategy = "deterministic"
    translate_fields = ["question", "options.*", "answer"]
    source_name = "Open Trivia DB"
    source_url = "https://opentdb.com/"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            j = r.json()

        results = j.get("results") or []
        if not results:
            return {"question": "", "options": [], "answer": "", "category": ""}
        q = results[0]
        correct = _html.unescape(q.get("correct_answer", ""))
        opts = [_html.unescape(o) for o in q.get("incorrect_answers") or []]
        opts.append(correct)
        random.shuffle(opts)
        return {
            "question": _html.unescape(q.get("question", "")),
            "category": q.get("category", ""),
            "difficulty": q.get("difficulty", ""),
            "options": opts,
            "answer": correct,
        }
