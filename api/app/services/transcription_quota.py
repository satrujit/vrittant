"""Per-reporter monthly STT quota.

Tracks live-dictation seconds consumed per reporter and rolls the
counter atomically when the calendar month flips. Cap is configured
per-user via the ``users.monthly_transcription_limit`` column (in
HOURS). Default is 3 h/month — enough for typical reporter usage,
caps the worst-case "mic left on for an afternoon" failure mode.

Why not a separate ``transcription_usage`` table:
- v1 only needs current-month counter, no historical breakdown
- two columns on ``users`` is one less migration + one less join
- if we later want monthly history, we can backfill into a new table
  by archiving the counter on first-of-month — additive change

Concurrency model: every quota mutation goes through ``add_usage``
which uses ``UPDATE ... WHERE id = ...`` with row-level locking via
SELECT FOR UPDATE inside a transaction. Two concurrent live sessions
ending at the same instant will serialise on the row lock; neither
loses its increment.
"""
from __future__ import annotations

import logging
from typing import TypedDict

from sqlalchemy.orm import Session

from ..models.user import User
from ..utils.tz import now_ist


logger = logging.getLogger(__name__)


def _current_month() -> str:
    """Return the IST year-month identifier (e.g., ``"2026-05"``).

    IST is the boundary that matters for reporters — the counter
    flips at midnight IST on the 1st, not midnight UTC.
    """
    return now_ist().strftime("%Y-%m")


class QuotaStatus(TypedDict):
    used_seconds: int
    limit_hours: int
    limit_seconds: int
    remaining_seconds: int
    is_over_quota: bool
    year_month: str


def get_status(db: Session, user: User) -> QuotaStatus:
    """Return the user's current-month quota status.

    Performs an in-memory month-rollover check WITHOUT writing to the
    DB — pure read. The actual reset of the stored counter happens
    inside ``add_usage`` on first usage of a new month, so a long
    period of inactivity at the boundary doesn't leave a stale
    counter visible to ``get_status`` callers.
    """
    current = _current_month()
    if user.transcription_usage_month and user.transcription_usage_month == current:
        used = int(user.transcription_seconds_used or 0)
    else:
        # New month (or never-used) — caller sees a fresh budget
        # immediately, even though the row hasn't been rewritten yet.
        used = 0
    limit_hours = int(user.monthly_transcription_limit or 0)
    limit_seconds = limit_hours * 3600
    remaining = max(0, limit_seconds - used)
    return {
        "used_seconds": used,
        "limit_hours": limit_hours,
        "limit_seconds": limit_seconds,
        "remaining_seconds": remaining,
        "is_over_quota": used >= limit_seconds,
        "year_month": current,
    }


def is_over_quota(db: Session, user: User) -> bool:
    """Cheap check used at WS-accept time before starting a session.

    Doesn't lock the row — false negatives at the boundary (user
    starts a session that pushes them over) are acceptable; we cut at
    session start, not mid-session.
    """
    return get_status(db, user)["is_over_quota"]


def add_usage(db: Session, *, user_id: str, seconds: int) -> None:
    """Atomically increment the user's current-month usage counter.

    Resets the counter if the stored ``transcription_usage_month``
    doesn't match the current IST month. The reset+increment happens
    within a single transaction guarded by SELECT FOR UPDATE so two
    sessions ending simultaneously can't double-reset or lose either
    increment.

    No-op if ``seconds <= 0``.
    """
    if seconds <= 0:
        return
    current = _current_month()
    try:
        # Lock the row for the duration of this transaction. PostgreSQL
        # serialises concurrent UPDATEs naturally; the explicit lock
        # closes the read-then-write race in case another session is
        # observing the same row mid-rollover.
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .one_or_none()
        )
        if user is None:
            logger.warning("transcription_quota.add_usage: user %s missing", user_id)
            return
        if user.transcription_usage_month != current:
            user.transcription_seconds_used = seconds
            user.transcription_usage_month = current
        else:
            user.transcription_seconds_used = (
                int(user.transcription_seconds_used or 0) + seconds
            )
        db.commit()
    except Exception:
        db.rollback()
        # Log + swallow — quota is best-effort, must never block STT
        # commit on its own failure. Worst case: a few seconds of
        # usage isn't counted; if the bug is sustained, the
        # under-counting trends will show up in our session-end logs.
        logger.exception(
            "transcription_quota.add_usage failed (user=%s, seconds=%d)",
            user_id, seconds,
        )
