"""Shared timezone constants for the Vrittant backend.

All timestamps should be stored and compared in IST (UTC+05:30).
"""

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Return the current time in IST."""
    return datetime.now(IST)
