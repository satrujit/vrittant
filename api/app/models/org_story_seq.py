"""Per-org sequential counter for story display IDs.

Production schema is created via the 2026-04-29-story-display-id.sql
migration. This SQLAlchemy model exists so test databases (SQLite,
built from `Base.metadata.create_all()`) get the same table without
re-running the SQL migration.
"""
from sqlalchemy import BigInteger, Column, ForeignKey, String

from ..database import Base


class OrgStorySeq(Base):
    __tablename__ = "org_story_seq"

    organization_id = Column(
        String,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_seq = Column(BigInteger, nullable=False)
