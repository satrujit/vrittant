from typing import Optional
from pydantic import BaseModel, Field, model_validator


# ── User management ──

class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=10, max_length=16, pattern=r'^\+\d{10,15}$')
    email: Optional[str] = None
    area_name: str = ""
    user_type: str = Field(default="reporter", pattern=r'^(reporter|reviewer)$')
    categories: list[str] = []
    regions: list[str] = []

    @model_validator(mode="after")
    def _reporter_requires_area(self):
        if self.user_type == "reporter" and not (self.area_name and self.area_name.strip()):
            raise ValueError("area_name is required for reporters")
        return self


class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[str] = None
    area_name: Optional[str] = None
    is_active: Optional[bool] = None
    categories: Optional[list[str]] = None
    regions: Optional[list[str]] = None


class UpdateUserRoleRequest(BaseModel):
    user_type: str = Field(..., pattern=r'^(reporter|reviewer)$')


class UpdateUserEntitlementsRequest(BaseModel):
    page_keys: list[str]


class UserManagementResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    user_type: str
    area_name: str
    is_active: bool
    entitlements: list[str] = []
    categories: list[str] = []
    regions: list[str] = []

    model_config = {"from_attributes": True}


# ── Org management ──

class UpdateOrgRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    theme_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    logo_url: Optional[str] = None
    theme_color: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Master data config ──

class CategoryItem(BaseModel):
    key: str
    label: str
    label_local: str = ""
    is_active: bool = True


class PublicationTypeItem(BaseModel):
    key: str
    label: str
    label_local: str = ""
    is_active: bool = True


class PageSuggestionItem(BaseModel):
    name: str
    name_local: str = ""
    sort_order: int = 0
    is_active: bool = True


class PriorityLevelItem(BaseModel):
    key: str
    label: str
    label_local: str = ""
    is_active: bool = True


class UpdateOrgConfigRequest(BaseModel):
    categories: Optional[list[CategoryItem]] = None
    publication_types: Optional[list[PublicationTypeItem]] = None
    page_suggestions: Optional[list[PageSuggestionItem]] = None
    priority_levels: Optional[list[PriorityLevelItem]] = None
    default_language: Optional[str] = None


class OrgConfigResponse(BaseModel):
    categories: list[dict] = []
    publication_types: list[dict] = []
    page_suggestions: list[dict] = []
    priority_levels: list[dict] = []
    default_language: str = "odia"

    model_config = {"from_attributes": True}
