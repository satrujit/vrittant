from datetime import datetime
from typing import Optional

from pydantic import BaseModel

class ParagraphSchema(BaseModel):
    id: str
    text: str = ""
    photo_path: Optional[str] = None
    media_path: Optional[str] = None
    media_type: Optional[str] = None   # photo | video | audio | document
    media_name: Optional[str] = None
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

class RevisionResponse(BaseModel):
    id: str
    story_id: str
    editor_id: str
    headline: str
    paragraphs: list[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
