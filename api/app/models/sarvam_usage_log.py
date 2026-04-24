"""SQLAlchemy model for the Sarvam AI per-call cost ledger.

Schema lives in `api/migrations/2026-04-24-sarvam-usage-log.sql`. The model
mirrors that table for ORM access, but inserts go through
``services/sarvam_client.py`` (which constructs raw rows in a single
INSERT to keep instrumentation overhead low).

Backend-only. No API endpoint exposes this table — query directly via psql
or write ad-hoc analysis scripts.
"""
from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    BigInteger,
    Numeric,
    String,
    Text,
)

from ..database import Base
from ..utils.tz import now_ist


class SarvamUsageLog(Base):
    __tablename__ = "sarvam_usage_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=now_ist, nullable=False)

    service = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    endpoint = Column(Text)

    input_tokens = Column(Integer)
    cached_tokens = Column(Integer)
    output_tokens = Column(Integer)
    characters = Column(Integer)
    audio_seconds = Column(Integer)
    pages = Column(Integer)

    cost_inr = Column(Numeric(10, 4), nullable=False)

    story_id = Column(String, ForeignKey("stories.id", ondelete="SET NULL"))
    bucket = Column(Text)
    user_id = Column(String)

    duration_ms = Column(Integer)
    status_code = Column(Integer)
    error = Column(Text)
