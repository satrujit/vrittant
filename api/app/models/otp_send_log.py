"""Per-phone OTP send log — used to rate-limit `/auth/request-otp` and
`/auth/resend-otp` so a misbehaving client (or attacker) can't burn money
sending OTPs in a tight loop.

Why a table and not in-memory: Cloud Run autoscales horizontally; an
in-memory counter on each instance would let a user send N × instance_count
OTPs before any single instance noticed. A tiny Postgres table keeps the
limit honest across instances and gives us an audit trail for free.

Cleanup: rows older than the longest rate-limit window (1 hour) are useless.
A daily DELETE in the existing scheduled-tasks sweep keeps the table small;
short-term we tolerate unbounded growth — at ~1 row per OTP send and
realistic reporter volume this stays under a few thousand rows even without
cleanup.
"""

from sqlalchemy import Column, DateTime, Integer, String, Index

from ..database import Base
from ..utils.tz import now_ist


class OtpSendLog(Base):
    __tablename__ = "otp_send_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String, nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), default=now_ist, nullable=False)

    __table_args__ = (
        Index("ix_otp_send_log_phone_sent_at", "phone", "sent_at"),
    )
