from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import create_access_token, get_current_user
from ..models.otp_send_log import OtpSendLog
from ..models.user import User
from ..schemas.auth import (
    MSG91LoginRequest,
    OTPRequest,
    OTPResend,
    OTPVerify,
    Token,
    UserResponse,
)
from ..services.msg91 import verify_access_token
from ..services.otp_provider import (
    send_otp as otp_send,
    verify_otp as otp_verify,
    resend_otp as otp_resend,
)
from ..utils.tz import now_ist

router = APIRouter()


# ── Test bypass ────────────────────────────────────────────────────────────
# In dev and UAT we accept a hardcoded OTP and skip the paid SMS provider
# entirely. This is so QA / emulator runs don't burn Twilio (~₹14/OTP) credits
# every time someone taps "Send OTP". Production (`ENV=production`) ignores
# this branch — real OTP, real spend.
#
# Codes:
#   dev:  000000  (existing)
#   uat:  000111  (new — keeps prod-like flow but free)
_TEST_OTP_CODES = {
    "dev": "000000",
    "uat": "000111",
}


def _is_test_env() -> bool:
    return settings.ENV in _TEST_OTP_CODES


def _expected_test_otp() -> str:
    return _TEST_OTP_CODES.get(settings.ENV, "")


# ── OTP rate limit ─────────────────────────────────────────────────────────
# Each provider call costs real money (~₹0.20 MSG91, ~₹4 Twilio Verify, more
# without DLT). We cap per-phone send frequency so a buggy client, double-tap,
# or attacker can't burn the budget. Limits chosen to be invisible to a real
# reporter typing in their phone but visible to anything looping.
#
# - Min gap between sends: 60s  (covers double-tap and rage-clicks)
# - Max sends per hour:    5   (covers genuine OTP-not-arrived retries with
#                                 voice/SMS while still capping daily damage)
#
# Rationale for using DB rather than in-memory: Cloud Run autoscales; an
# in-memory dict on each instance would let a user send N×instance_count
# OTPs before any single instance noticed.
_OTP_MIN_GAP_SECONDS = 60
_OTP_MAX_PER_HOUR = 5


def _enforce_otp_rate_limit(db: Session, phone: str) -> None:
    """Raise 429 if the phone has hit either limit. Fail-open if the table
    isn't migrated yet so a missed migration can't take auth offline."""
    try:
        now = now_ist()
        hour_ago = now - timedelta(hours=1)
        recent = (
            db.query(OtpSendLog)
            .filter(OtpSendLog.phone == phone, OtpSendLog.sent_at >= hour_ago)
            .order_by(OtpSendLog.sent_at.desc())
            .all()
        )
    except Exception as exc:
        # Most likely cause: migration hasn't been applied. Logging loudly
        # so it's caught in Cloud Run logs, but we don't block users.
        import logging as _logging
        _logging.getLogger("auth.otp").warning(
            "otp rate-limit query failed (table missing?): %s", exc
        )
        return

    if recent:
        last_gap = (now - recent[0].sent_at).total_seconds()
        if last_gap < _OTP_MIN_GAP_SECONDS:
            retry_after = int(_OTP_MIN_GAP_SECONDS - last_gap) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {retry_after}s before requesting another OTP",
                headers={"Retry-After": str(retry_after)},
            )

    if len(recent) >= _OTP_MAX_PER_HOUR:
        # Tell the client when the oldest in-window send falls out so the
        # Retry-After header is accurate.
        oldest = recent[-1].sent_at
        retry_after = int((oldest + timedelta(hours=1) - now).total_seconds()) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Hourly OTP limit reached. Try again later.",
            headers={"Retry-After": str(max(retry_after, 60))},
        )


def _record_otp_send(db: Session, phone: str) -> None:
    """Record a successful provider call. Best-effort — a failure here
    means the next request from this phone won't see this send in its
    rate-limit query, which is preferable to 500'ing a successful OTP."""
    try:
        db.add(OtpSendLog(phone=phone))
        db.commit()
    except Exception as exc:
        import logging as _logging
        _logging.getLogger("auth.otp").warning(
            "otp send-log insert failed: %s", exc
        )
        db.rollback()


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
    """Send OTP for mobile clients. Provider chosen via OTP_PROVIDER env."""
    user = db.query(User).filter(User.phone == body.phone, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # Test-env short-circuit: skip the paid provider entirely. Verify-otp
    # accepts the corresponding hardcoded code below.
    if _is_test_env():
        return {"message": "OTP sent (test)", "phone": body.phone, "req_id": "test"}

    # Cap per-phone send rate before hitting the paid provider.
    _enforce_otp_rate_limit(db, body.phone)

    import logging as _logging
    _log = _logging.getLogger("auth.otp")
    try:
        data = await otp_send(body.phone)
    except Exception as exc:
        _log.warning("send_otp failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to send OTP")

    _record_otp_send(db, body.phone)
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

    # Test-env bypass — see _TEST_OTP_CODES at top of file.
    if _is_test_env() and body.otp == _expected_test_otp():
        token = create_access_token(user.id, user.user_type)
        return Token(access_token=token)

    import logging as _logging
    _log = _logging.getLogger("auth.otp")
    try:
        await otp_verify(body.phone, body.otp, req_id=body.req_id)
    except Exception as exc:
        _log.warning("verify_otp failed: %s", exc)
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

    # Test-env short-circuit (same as request-otp).
    if _is_test_env():
        return {"message": "OTP resent (test)", "phone": body.phone}

    # Resend is a paid send too — same caps apply. (For Twilio Verify the
    # underlying call is literally another `Verifications` POST; for MSG91
    # it's `retryOtp` which still bills.)
    _enforce_otp_rate_limit(db, body.phone)

    import logging as _logging
    _log = _logging.getLogger("auth.otp")
    try:
        await otp_resend(body.phone, req_id=body.req_id)
    except Exception as exc:
        _log.warning("resend_otp failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to resend OTP")

    _record_otp_send(db, body.phone)
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
