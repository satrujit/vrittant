import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database import Base


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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    story = relationship("Story", back_populates="revision")
    editor = relationship("User")
