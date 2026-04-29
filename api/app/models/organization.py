import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String

from ..database import Base
from ..utils.tz import now_ist


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, nullable=False, unique=True)
    # Short uppercase prefix for human-readable story display IDs
    # (e.g. "PNS" → "PNS-26-1234"). NOT NULL is enforced at the prod DB
    # level via the 2026-04-29 migration; the column is left nullable
    # here so test orgs (built from create_all on SQLite) don't have to
    # set it. The display_id property gracefully returns None when this
    # is missing, so callers fall back to the UUID.
    display_code = Column(String, nullable=True)
    logo_url = Column(String, nullable=True, default="")
    theme_color = Column(String, nullable=True, default="#FA6C38")
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime, default=now_ist
    )
    updated_at = Column(
        DateTime,
        default=now_ist,
        onupdate=now_ist,
    )
