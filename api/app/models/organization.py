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
