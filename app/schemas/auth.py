from typing import Optional
from pydantic import BaseModel, Field


class OTPRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=16, pattern=r'^\+\d{10,15}$')


class OTPVerify(BaseModel):
    phone: str = Field(..., min_length=10, max_length=16, pattern=r'^\+\d{10,15}$')
    otp: str = Field(..., min_length=4, max_length=8)


class FirebaseLoginRequest(BaseModel):
    firebase_token: str = Field(..., min_length=10, max_length=5000)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EntitlementResponse(BaseModel):
    page_key: str

    model_config = {"from_attributes": True}


class OrgInfo(BaseModel):
    id: str
    name: str
    slug: str
    logo_url: Optional[str] = None
    theme_color: Optional[str] = None

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    user_type: str
    area_name: str
    organization: str
    organization_id: Optional[str] = None
    org: Optional[OrgInfo] = None
    entitlements: list[EntitlementResponse] = []

    model_config = {"from_attributes": True}
