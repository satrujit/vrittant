import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from ..database import Base
from ..utils.tz import now_ist


class VoiceEnrollment(Base):
    __tablename__ = "voice_enrollments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    # JSON-encoded list of floats (speaker embedding from CAM++ model)
    embedding = Column(Text, nullable=False)
    sample_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_ist)
    updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)
