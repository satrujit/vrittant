from typing import Optional
from pydantic import BaseModel


class OTPRequest(BaseModel):
    phone: str


class OTPVerify(BaseModel):
    phone: str
    otp: str


class FirebaseLoginRequest(BaseModel):
    firebase_token: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EntitlementResponse(BaseModel):
    page_key: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    user_type: str
    area_name: str
    organization: str
    entitlements: list[EntitlementResponse] = []

    model_config = {"from_attributes": True}
