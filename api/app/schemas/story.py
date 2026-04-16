from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_serializer

from ..utils.tz import IST

class ParagraphSchema(BaseModel):
    id: str
    text: str = ""
    photo_path: Optional[str] = None
    media_path: Optional[str] = None
    media_type: Optional[str] = None   # photo | video | audio | document
    media_name: Optional[str] = None
    table_data: Optional[list[list[str]]] = None  # 2D array for table paragraphs
    created_at: Optional[str] = None

class StoryCreate(BaseModel):
    headline: str = ""
    category: Optional[str] = None
    location: Optional[str] = None
    paragraphs: list[ParagraphSchema] = []

class StoryUpdate(BaseModel):
    headline: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    paragraphs: Optional[list[ParagraphSchema]] = None

class StoryResponse(BaseModel):
    id: str
    reporter_id: str
    headline: str
    category: Optional[str]
    location: Optional[str]
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at", "submitted_at")
    @classmethod
    def serialize_ist(cls, v: datetime | None) -> str | None:
        if v is None:
            return None
        # DB stores naive IST values; tag with +05:30 so clients parse correctly
        if v.tzinfo is None:
            v = v.replace(tzinfo=IST)
        return v.isoformat()

class RevisionResponse(BaseModel):
    id: str
    story_id: str
    editor_id: str
    headline: str
    paragraphs: list[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    @classmethod
    def serialize_ist(cls, v: datetime | None) -> str | None:
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=IST)
        return v.isoformat()
