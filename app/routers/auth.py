from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import create_access_token, get_current_user
from ..models.user import User
from ..firebase_admin_setup import verify_firebase_token
from ..schemas.auth import FirebaseLoginRequest, OTPRequest, OTPVerify, Token, UserResponse

router = APIRouter()


@router.post("/check-phone")
def check_phone(body: OTPRequest, db: Session = Depends(get_db)):
    """Check if a phone number is registered before sending OTP."""
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    return {"registered": True}


@router.post("/request-otp")
def request_otp(body: OTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    return {"message": "OTP sent", "phone": body.phone}


@router.post("/verify-otp", response_model=Token)
def verify_otp(body: OTPVerify, db: Session = Depends(get_db)):
    if settings.ENV == "prod":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Dev-only: accept any OTP in development mode
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    token = create_access_token(user.id, user.user_type)
    return Token(access_token=token)


@router.post("/firebase-login", response_model=Token)
def firebase_login(body: FirebaseLoginRequest, db: Session = Depends(get_db)):
    """
    Verify a Firebase ID token and issue a backend JWT.
    The user must already exist in the database (no auto-registration).
    """
    try:
        decoded = verify_firebase_token(body.firebase_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase token",
        )

    # Firebase phone auth puts the phone in the token claims
    phone = decoded.get("phone_number")
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase token does not contain a phone number",
        )

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not registered. Contact admin for access.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Eagerly load org and entitlements for the token response
    db.refresh(user, ["org", "entitlements"])

    token = create_access_token(user.id, user.user_type)
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Eagerly load org and entitlements so the response includes org info
    db.refresh(user, ["org", "entitlements"])
    return user
