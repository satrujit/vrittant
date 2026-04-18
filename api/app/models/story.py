import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from ..database import Base
from ..utils.tz import now_ist


def build_search_text(headline: str | None, paragraphs: list | None, location: str | None) -> str:
    """Flatten story fields into a single searchable text string."""
    parts = []
    if headline:
        parts.append(headline)
    if location:
        parts.append(location)
    if paragraphs:
        for p in paragraphs:
            if isinstance(p, dict):
                txt = p.get("text", "")
                if txt:
                    parts.append(txt)
            elif isinstance(p, str):
                parts.append(p)
    return " ".join(parts)


class Story(Base):
    __tablename__ = "stories"
    __table_args__ = (
        Index("ix_stories_org_status_submitted", "organization_id", "status", "submitted_at"),
        Index("ix_stories_deleted_at", "deleted_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    reporter_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    headline = Column(String, default="")
    category = Column(String, nullable=True)
    location = Column(String, nullable=True)
    paragraphs = Column(JSON, default=list)
    status = Column(String, default="draft")  # draft | submitted | approved | published | rejected
    priority = Column(String, nullable=True, default="normal")  # normal | urgent | breaking
    source = Column(String, nullable=True)  # URL for auto-generated, "Reporter Submitted", "Editor Created"
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)
    deleted_at = Column(DateTime, nullable=True, default=None)
    search_text = Column(Text, default="", server_default="")  # denormalized text for trigram search
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    assigned_match_reason = Column(String, nullable=True)  # category | region | load_balance | manual

    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="stories")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    revision = relationship("StoryRevision", back_populates="story", uselist=False)

    def refresh_search_text(self):
        """Update search_text from current headline, paragraphs, location."""
        self.search_text = build_search_text(self.headline, self.paragraphs, self.location)
