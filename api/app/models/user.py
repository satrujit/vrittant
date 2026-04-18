import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from ..database import Base
from ..utils.tz import now_ist


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=True)
    user_type = Column(String, nullable=False, default="reporter")  # reporter | reviewer | org_admin
    area_name = Column(String, nullable=False, default="")
    categories = Column(JSON, nullable=False, default=list)  # reviewer beats
    regions = Column(JSON, nullable=False, default=list)     # reviewer beats
    organization = Column(String, nullable=False, default="")
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(
        DateTime,
        default=now_ist,
        onupdate=now_ist,
    )
    deleted_at = Column(DateTime, nullable=True, default=None)

    org = relationship("Organization")
    stories = relationship("Story", foreign_keys="Story.reporter_id", back_populates="reporter")
    entitlements = relationship("Entitlement", back_populates="user", cascade="all, delete-orphan")


class Entitlement(Base):
    __tablename__ = "entitlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    page_key = Column(String, nullable=False)

    user = relationship("User", back_populates="entitlements")
