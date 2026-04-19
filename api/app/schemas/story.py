from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, field_serializer

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
    assigned_to: Optional[str] = None
    assigned_match_reason: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at", "submitted_at")
    @classmethod
    def serialize_utc(cls, v: datetime | None) -> str | None:
        if v is None:
            return None
        # DB columns are naive `DateTime`. now_ist() returns tz-aware IST,
        # but psycopg2 converts tz-aware → UTC and strips the tz when writing
        # to a naive column, so what's actually on disk is UTC wall-clock.
        # Tag as UTC (not IST) so clients parse to the correct moment.
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
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
    def serialize_utc(cls, v: datetime | None) -> str | None:
        if v is None:
            return None
        # See StoryResponse.serialize_utc — DB stores naive UTC values.
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()
