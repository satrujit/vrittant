import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text

from ..database import Base
from ..utils.tz import now_ist


class StoryComment(Base):
    """Editorial comments on a story — visible to reviewers/admins.

    Flat list (no threading). Created via POST /admin/stories/{id}/comments,
    listed via GET /admin/stories/{id}/comments. Authored by any reviewer
    or admin in the story's organization.
    """
    __tablename__ = "story_comments"
    __table_args__ = (
        Index("ix_story_comments_story_id_created", "story_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    story_id = Column(String, ForeignKey("stories.id"), nullable=False)
    author_id = Column(String, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=now_ist, nullable=False)
