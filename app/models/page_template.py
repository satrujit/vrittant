import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, JSON, String, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class PageTemplate(Base):
    __tablename__ = "page_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    paper_size = Column(String, default="broadsheet")
    width_mm = Column(Float, nullable=False)
    height_mm = Column(Float, nullable=False)
    zones = Column(JSON, nullable=False, default=list)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    creator = relationship("User")
