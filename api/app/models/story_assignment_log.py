import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String

from ..database import Base
from ..utils.tz import now_ist


class StoryAssignmentLog(Base):
    __tablename__ = "story_assignment_log"
    __table_args__ = (
        Index("ix_story_assignment_log_story_id", "story_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id = Column(String, ForeignKey("stories.id"), nullable=False)
    from_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    to_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    assigned_by = Column(String, ForeignKey("users.id"), nullable=True)  # null = system
    reason = Column(String, nullable=False)  # auto | manual | reviewer_deactivated
    created_at = Column(DateTime, default=now_ist, nullable=False)
