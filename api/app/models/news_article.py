"""News articles fetched from external APIs (e.g. Mediastack)."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Index
from ..database import Base
from ..utils.tz import now_ist


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String, nullable=False, unique=True)
    source = Column(String, nullable=True)
    author = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    category = Column(String, nullable=True)
    language = Column(String(5), nullable=True)
    country = Column(String(5), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=now_ist)

    __table_args__ = (
        Index("ix_news_articles_published_at", "published_at"),
        Index("ix_news_articles_source", "source"),
        # Composite (category, published_at) covers any "WHERE category = ?"
        # lookup too, so a standalone category index would be redundant.
        Index("ix_news_articles_cat_pub", "category", "published_at"),
        # Note: dropped ix_news_articles_category (covered by cat_pub) and
        # ix_news_articles_country (always 'IN', zero discriminating power)
        # in 2026-04-30-news-articles-index-cleanup.sql — see that migration
        # for context.
    )
