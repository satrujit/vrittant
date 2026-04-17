from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import create_access_token, get_current_user
from ..models.user import User
from ..schemas.auth import (
    MSG91LoginRequest,
    OTPRequest,
    OTPResend,
    OTPVerify,
    Token,
    UserResponse,
)
from ..services.msg91 import (
    verify_access_token,
    send_otp as msg91_send,
    verify_otp as msg91_verify,
    resend_otp as msg91_resend,
)

router = APIRouter()


# ── Phone check ──

@router.post("/check-phone")
def check_phone(body: OTPRequest, db: Session = Depends(get_db)):
    """Check if a phone number is registered. Returns widget config on success."""
    user = db.query(User).filter(User.phone == body.phone, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    return {
        "registered": True,
        "widget": {
            "widgetId": settings.MSG91_WIDGET_ID,
            "tokenAuth": settings.MSG91_TOKEN_AUTH,
        },
    }


# ── Direct OTP endpoints (mobile) ──

@router.post("/request-otp")
async def request_otp(body: OTPRequest, db: Session = Depends(get_db)):
    """Send OTP via MSG91 (for mobile clients). Returns reqId for verify/resend."""
    user = db.query(User).filter(User.phone == body.phone, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    import logging as _logging
    _log = _logging.getLogger("auth.msg91")
    try:
        data = await msg91_send(body.phone)
    except Exception as exc:
        _log.warning("MSG91 send_otp failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to send OTP")

    req_id = data.get("reqId") or data.get("request_id") or ""
    return {"message": "OTP sent", "phone": body.phone, "req_id": req_id}


@router.post("/verify-otp", response_model=Token)
async def verify_otp(body: OTPVerify, db: Session = Depends(get_db)):
    """Verify OTP via MSG91 and issue JWT (for mobile clients)."""
    user = db.query(User).filter(User.phone == body.phone, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # Dev bypass
    if settings.ENV == "dev" and body.otp == "000000":
        token = create_access_token(user.id, user.user_type)
        return Token(access_token=token)

    import logging as _logging
    _log = _logging.getLogger("auth.msg91")
    try:
        await msg91_verify(body.phone, body.otp, req_id=body.req_id)
    except Exception as exc:
        _log.warning("MSG91 verify_otp failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP verification failed")

    token = create_access_token(user.id, user.user_type)
    return Token(access_token=token)


@router.post("/resend-otp")
async def resend_otp(body: OTPResend, db: Session = Depends(get_db)):
    """Resend OTP via MSG91 (for mobile clients)."""
    user = db.query(User).filter(User.phone == body.phone, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    import logging as _logging
    _log = _logging.getLogger("auth.msg91")
    try:
        await msg91_resend(body.phone, req_id=body.req_id)
    except Exception as exc:
        _log.warning("MSG91 resend_otp failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to resend OTP")

    return {"message": "OTP resent", "phone": body.phone}


# ── Widget token login (web) ──

def _extract_verified_mobile(msg91_response: dict) -> str | None:
    """Pull the verified mobile out of MSG91's verifyAccessToken response.

    MSG91 returns the verified mobile in different shapes depending on
    integration. Known shapes:
      {"type":"success","message":"919999999999"}
      {"type":"success","data":{"mobile":"919999999999"}}
      {"type":"success","data":{"message":"919999999999"}}
    """
    if not isinstance(msg91_response, dict):
        return None
    data = msg91_response.get("data")
    if isinstance(data, dict):
        for key in ("mobile", "message"):
            v = data.get(key)
            if isinstance(v, str) and v.strip().isdigit():
                return v.strip()
    msg = msg91_response.get("message")
    if isinstance(msg, str) and msg.strip().isdigit() and len(msg.strip()) >= 10:
        return msg.strip()
    return None


@router.post("/msg91-login", response_model=Token)
async def msg91_login(body: MSG91LoginRequest, db: Session = Depends(get_db)):
    """Verify MSG91 OTP Widget access token and issue JWT (for web clients).

    Security: the verified mobile from MSG91 must match body.phone, otherwise
    an attacker who completed OTP for their own phone could submit any other
    phone in body.phone to take over that account.
    """
    import logging as _logging
    _log = _logging.getLogger("auth.msg91")
    try:
        msg91_response = await verify_access_token(body.access_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MSG91 token",
        )

    # Bind the verified mobile to body.phone — fail closed if it's missing.
    verified_mobile = _extract_verified_mobile(msg91_response)
    requested_mobile = body.phone.lstrip("+").strip()
    if not verified_mobile or verified_mobile != requested_mobile:
        _log.warning(
            "MSG91 phone-binding mismatch (verified=%s vs requested=%s)",
            verified_mobile, requested_mobile,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MSG91 token",
        )

    user = db.query(User).filter(User.phone == body.phone, User.deleted_at.is_(None)).first()
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
    # Only reviewers and org_admins can access the web panel
    if user.user_type not in ("reviewer", "org_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reporter accounts cannot access the review panel. Please use the mobile app.",
        )

    token = create_access_token(user.id, user.user_type)
    return Token(access_token=token)


# ── Current user ──

@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.refresh(user, ["org", "entitlements"])
    return user
