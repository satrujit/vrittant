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

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.models.story import Story
from app.utils.tz import now_ist

from app.services.whatsapp import outbound, i18n


_OPEN_APP_URL = "https://vrittant.in/r/today"
_HEADLINE_MAX = 50
_LIST_CAP = 25


def list_for_reporter(db: Session, reporter_id: str) -> List[Story]:
    """Return today-IST stories for `reporter_id`, newest activity first.

    Story.submitted_at / updated_at are `Column(DateTime)` (timezone-
    naive) but written from `now_ist()` (tz-aware IST). SQLAlchemy
    strips tzinfo on write, so the columns hold IST WALL-CLOCK time as
    naive values.

    Boundary math: build naive IST midnights for [today, tomorrow) and
    compare directly. The previous implementation subtracted 5:30 from
    the IST boundaries (treating the column as UTC) which shifted the
    window 5:30 hours back — today's evening submissions were excluded
    and yesterday's evening submissions were included.

    Inclusion rule: `submitted_at` falls in [today, tomorrow), OR the
    story was *appended to today* via WhatsApp add-mode. Without the
    second clause a reporter who tapped "➕ Add more" on a yesterday
    story and forwarded a follow-up today would see "no stories filed
    today" — confusing and the actual prod complaint we fixed in
    response to the 2026-05-07 UAT report. We use `updated_at` as a
    proxy; it's bumped by reviewer edits too, but reporter accounts
    only see their own stories so the only realistic non-WhatsApp
    bumper is the reporter editing their own draft, which we still
    want to surface in "today's stories".

    Order: most-recently-touched first (NULLs-last), so a story
    appended-to today comes before a stale older submission.
    """
    today = now_ist().date()
    start_naive = datetime(today.year, today.month, today.day)
    end_naive = start_naive + timedelta(days=1)

    submitted_today = and_(
        Story.submitted_at >= start_naive,
        Story.submitted_at < end_naive,
    )
    updated_today = and_(
        Story.updated_at >= start_naive,
        Story.updated_at < end_naive,
    )
    rows = (
        db.query(Story)
        .filter(
            Story.reporter_id == reporter_id,
            Story.deleted_at.is_(None),
            Story.status == "submitted",
            or_(submitted_today, updated_today),
        )
        .order_by(
            func.coalesce(Story.updated_at, Story.submitted_at, Story.created_at).desc(),
        )
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
