from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class EditionCreate(BaseModel):
    publication_date: date
    paper_type: str = "daily"
    title: Optional[str] = None


class EditionUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    publication_date: Optional[date] = None
    paper_type: Optional[str] = None


class EditionPageCreate(BaseModel):
    page_name: str
    page_number: Optional[int] = None


class EditionPageUpdate(BaseModel):
    page_name: Optional[str] = None
    sort_order: Optional[int] = None


class StoryAssignmentUpdate(BaseModel):
    story_ids: list[str]


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class EditionPageStoryResponse(BaseModel):
    id: str
    story_id: str
    sort_order: int

    model_config = {"from_attributes": True}


class EditionPageResponse(BaseModel):
    id: str
    page_number: int
    page_name: str
    sort_order: int
    story_count: int = 0
    story_assignments: list[EditionPageStoryResponse] = []

    model_config = {"from_attributes": True}


class EditionResponse(BaseModel):
    id: str
    publication_date: date
    paper_type: str
    title: str
    status: str
    page_count: int = 0
    story_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EditionDetailResponse(EditionResponse):
    pages: list[EditionPageResponse] = []


class EditionListItemResponse(EditionResponse):
    """Edition list item — includes pages so the placement matrix can render
    page-name pickers without an extra round-trip per edition."""
    pages: list[EditionPageResponse] = []


class EditionListResponse(BaseModel):
    editions: list[EditionListItemResponse]
    total: int
