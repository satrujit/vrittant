import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from ..database import Base

class Story(Base):
    __tablename__ = "stories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    reporter_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    headline = Column(String, default="")
    category = Column(String, nullable=True)
    location = Column(String, nullable=True)
    paragraphs = Column(JSON, default=list)
    status = Column(String, default="draft")  # draft | submitted | approved | published | rejected
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    reporter = relationship("User", back_populates="stories")
    revision = relationship("StoryRevision", back_populates="story", uselist=False)
