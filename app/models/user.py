import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=True)
    user_type = Column(String, nullable=False, default="reporter")  # reporter | reviewer | admin
    area_name = Column(String, nullable=False, default="")
    organization = Column(String, nullable=False, default="")
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    org = relationship("Organization")
    stories = relationship("Story", back_populates="reporter")
    entitlements = relationship("Entitlement", back_populates="user", cascade="all, delete-orphan")


class Entitlement(Base):
    __tablename__ = "entitlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    page_key = Column(String, nullable=False)

    user = relationship("User", back_populates="entitlements")
