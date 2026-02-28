import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


class Edition(Base):
    __tablename__ = "editions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    publication_date = Column(Date, nullable=False)
    paper_type = Column(String, default="daily")  # daily | weekend | evening | special
    title = Column(String, nullable=False, default="")
    status = Column(String, default="draft")  # draft | finalized | published
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    pages = relationship(
        "EditionPage",
        back_populates="edition",
        cascade="all, delete-orphan",
        order_by="EditionPage.sort_order",
    )


class EditionPage(Base):
    __tablename__ = "edition_pages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    edition_id = Column(
        String, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number = Column(Integer, nullable=False)
    page_name = Column(String, nullable=False, default="")
    sort_order = Column(Integer, default=0)

    edition = relationship("Edition", back_populates="pages")
    story_assignments = relationship(
        "EditionPageStory",
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="EditionPageStory.sort_order",
    )


class EditionPageStory(Base):
    __tablename__ = "edition_page_stories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    edition_page_id = Column(
        String, ForeignKey("edition_pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    story_id = Column(
        String, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order = Column(Integer, default=0)

    page = relationship("EditionPage", back_populates="story_assignments")
