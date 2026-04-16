import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import relationship

from ..database import Base
from ..utils.tz import now_ist

DEFAULT_CATEGORIES = [
    {"key": "politics", "label": "Politics", "label_local": "ରାଜନୀତି", "is_active": True},
    {"key": "sports", "label": "Sports", "label_local": "କ୍ରୀଡ଼ା", "is_active": True},
    {"key": "crime", "label": "Crime", "label_local": "ଅପରାଧ", "is_active": True},
    {"key": "business", "label": "Business", "label_local": "ବ୍ୟବସାୟ", "is_active": True},
    {"key": "entertainment", "label": "Entertainment", "label_local": "ମନୋରଞ୍ଜନ", "is_active": True},
    {"key": "education", "label": "Education", "label_local": "ଶିକ୍ଷା", "is_active": True},
    {"key": "health", "label": "Health", "label_local": "ସ୍ୱାସ୍ଥ୍ୟ", "is_active": True},
    {"key": "technology", "label": "Technology", "label_local": "ପ୍ରଯୁକ୍ତି", "is_active": True},
]

DEFAULT_PUBLICATION_TYPES = [
    {"key": "daily", "label": "Daily", "is_active": True},
    {"key": "weekend", "label": "Weekend", "is_active": True},
    {"key": "evening", "label": "Evening", "is_active": True},
    {"key": "special", "label": "Special", "is_active": True},
]

DEFAULT_PAGE_SUGGESTIONS = [
    {"name": "Front Page", "sort_order": 1, "is_active": True},
    {"name": "Page 2", "sort_order": 2, "is_active": True},
    {"name": "Page 3", "sort_order": 3, "is_active": True},
    {"name": "Sports", "sort_order": 4, "is_active": True},
    {"name": "Entertainment", "sort_order": 5, "is_active": True},
    {"name": "State", "sort_order": 6, "is_active": True},
    {"name": "National", "sort_order": 7, "is_active": True},
    {"name": "International", "sort_order": 8, "is_active": True},
    {"name": "Editorial", "sort_order": 9, "is_active": True},
    {"name": "Classifieds", "sort_order": 10, "is_active": True},
]

DEFAULT_PRIORITY_LEVELS = [
    {"key": "normal", "label": "Normal", "label_local": "ସାଧାରଣ", "is_active": True},
    {"key": "urgent", "label": "Urgent", "label_local": "ଜରୁରୀ", "is_active": True},
    {"key": "breaking", "label": "Breaking", "label_local": "ବ୍ରେକିଂ", "is_active": True},
]


class OrgConfig(Base):
    __tablename__ = "org_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    categories = Column(JSON, nullable=False, default=list)
    publication_types = Column(JSON, nullable=False, default=list)
    page_suggestions = Column(JSON, nullable=False, default=list)
    priority_levels = Column(JSON, nullable=False, default=list)
    default_language = Column(String, nullable=False, default="odia")
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(
        DateTime,
        default=now_ist,
        onupdate=now_ist,
    )

    org = relationship("Organization")
