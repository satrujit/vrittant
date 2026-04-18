"""Idempotency tables for inbound webhook providers.

Gupshup retries on non-2xx responses (and occasionally on a flaky 2xx),
so we record every processed message_id and short-circuit duplicates.
"""
from sqlalchemy import Column, DateTime, String

from ..database import Base
from ..utils.tz import now_ist


class WhatsappInboundDedup(Base):
    __tablename__ = "whatsapp_inbound_dedup"

    message_id = Column(String, primary_key=True)
    received_at = Column(DateTime, default=now_ist, nullable=False)
