"""Today's-stories handler.

Renders the reporter's stories filed today as a plain-text message with
a CTA link to the mobile app.

Per the design: cap at 25 stories inline; if >25 show first 25 + a
`(+N more)` line + the same CTA URL. Headlines are truncated to 50
chars to keep the per-line width readable on small phone screens.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.models.story import Story
from app.utils.tz import now_ist, IST

from app.services.whatsapp import outbound, i18n


_OPEN_APP_URL = "https://vrittant.in/r/today"
_HEADLINE_MAX = 50
_LIST_CAP = 25


def list_for_reporter(db: Session, reporter_id: str) -> List[Story]:
    """Return today-IST stories for `reporter_id`, newest first.

    submitted_at is stored as a naive UTC DateTime in Postgres. To pick
    "today in IST", we compute the IST midnight boundaries and convert
    them to naive UTC for the comparison. Any submitted_at value (whether
    written naive-UTC or tz-aware via tests) compares correctly so long
    as we strip tzinfo from the boundaries.
    """
    now_in_ist = now_ist()
    today = now_in_ist.date()
    # IST boundaries as naive UTC.
    start_ist = datetime(today.year, today.month, today.day, tzinfo=IST)
    end_ist = start_ist + timedelta(days=1)
    # Convert to naive timestamps for comparison with the (typically
    # naive) submitted_at column. We keep tzinfo on these aware datetimes
    # because SQLAlchemy/SQLite will compare aware vs naive cleanly when
    # both are produced from the same Python datetime arithmetic the
    # tests use. To be safe across naive/aware mixes we drop tzinfo.
    start_naive = start_ist.astimezone(IST).replace(tzinfo=None) - timedelta(hours=5, minutes=30)
    end_naive = end_ist.astimezone(IST).replace(tzinfo=None) - timedelta(hours=5, minutes=30)

    rows = (
        db.query(Story)
        .filter(
            Story.reporter_id == reporter_id,
            Story.deleted_at.is_(None),
            Story.submitted_at >= start_naive,
            Story.submitted_at < end_naive,
        )
        .order_by(Story.created_at.desc())
        .all()
    )
    return rows


def render_today_message(stories: List[Story], lang: str) -> str:
    """Render the plain-text body. Empty list → empty-state message.
    Always includes the CTA URL except in the empty case (where there's
    nothing to view in the app)."""
    if not stories:
        return i18n.t("today.empty", lang)

    n = len(stories)
    header = i18n.t("today.header", lang, count=n)

    visible = stories[:_LIST_CAP]
    lines = []
    for s in visible:
        display_id = getattr(s, "display_id", None) or s.id
        h = (s.headline or "").strip()
        if len(h) > _HEADLINE_MAX:
            h = h[:_HEADLINE_MAX].rstrip() + "…"
        lines.append(f"• {display_id} — {h}")

    body_parts = [header, "", "\n".join(lines)]

    if n > _LIST_CAP:
        body_parts.append("")
        body_parts.append(i18n.t("today.overflow", lang, n=n - _LIST_CAP))

    body_parts.append("")
    body_parts.append(f"📱 {_OPEN_APP_URL}")

    return "\n".join(body_parts)


async def handle_today(*, db, sender_phone: str, user) -> None:
    """Public entry point used by the dispatcher when the today_list
    button is tapped or via menu list."""
    if user is None:
        return  # silent — only registered reporters get their list
    lang = i18n.resolve_lang(user)
    rows = list_for_reporter(db, user.id)
    body = render_today_message(rows, lang)
    await outbound.send_text(to=sender_phone, body=body)
