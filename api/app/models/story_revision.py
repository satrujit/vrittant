import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database import Base
from ..utils.tz import now_ist


class StoryRevision(Base):
    __tablename__ = "story_revisions"
    __table_args__ = (
        UniqueConstraint("story_id", name="uq_story_revisions_story_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id = Column(String, ForeignKey("stories.id"), nullable=False, index=True)
    editor_id = Column(String, ForeignKey("users.id"), nullable=False)
    headline = Column(String, nullable=False)
    paragraphs = Column(JSON, nullable=False, default=list)
    layout_config = Column(JSON, nullable=True, default=None)
    english_translation = Column(Text, nullable=True, default=None)
    social_posts = Column(JSON, nullable=True, default=None)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(
        DateTime,
        default=now_ist,
        onupdate=now_ist,
    )

    story = relationship("Story", back_populates="revision")
    editor = relationship("User")
