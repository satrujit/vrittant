import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, JSON, String, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base
from ..utils.tz import now_ist


class PageTemplate(Base):
    __tablename__ = "page_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    paper_size = Column(String, default="broadsheet")
    width_mm = Column(Float, nullable=False)
    height_mm = Column(Float, nullable=False)
    zones = Column(JSON, nullable=False, default=list)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(
        DateTime,
        default=now_ist,
        onupdate=now_ist,
    )

    creator = relationship("User")
