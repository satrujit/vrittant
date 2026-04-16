import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base
from ..utils.tz import now_ist


class LayoutTemplate(Base):
    __tablename__ = "layout_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    mode = Column(String, nullable=False, default="flexible")  # "fixed" or "flexible"
    html_content = Column(Text, nullable=False)
    thumbnail_url = Column(String, nullable=True)
    category = Column(String, nullable=True)
    organization_id = Column(
        String, ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(
        DateTime,
        default=now_ist,
        onupdate=now_ist,
    )

    creator = relationship("User")
