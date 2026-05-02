from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, get_db
from .models.user import User

security = HTTPBearer()


def create_access_token(user_id: str, user_type: str = "reporter") -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "user_type": user_type, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    return user


def get_current_org_id(user: User = Depends(get_current_user)) -> str:
    if not user.organization_id:
        raise HTTPException(status_code=403, detail="User is not assigned to any organization")
    return user.organization_id


def require_reviewer(user: User = Depends(get_current_user)) -> User:
    """Require authenticated user with reviewer or org_admin role."""
    if user.user_type not in ("reviewer", "org_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer access required")
    return user


def require_org_admin(user: User = Depends(get_current_user)) -> User:
    """Require authenticated user with org_admin role."""
    if user.user_type != "org_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Org admin access required")
    return user


# Backward-compat alias
get_current_reporter = get_current_user


# ---------------------------------------------------------------------------
# Lightweight auth — for endpoints that hold the request thread for seconds
# (LLM calls, long-poll). Same auth contract as get_current_user but uses an
# inline DB session that's opened and closed entirely inside this function,
# so the LLM await downstream doesn't hold a connection from the request-
# scoped pool.
#
# Why this matters: with pool_size=5 + overflow=3 = 8 connections per
# instance, a burst of 8 concurrent /api/llm/generate-story calls (each
# awaiting Gemini for 3-10s) would starve every other endpoint on that
# instance — including the /stories home-list refresh and /auth/me. Using
# this dependency on LLM endpoints releases the connection BEFORE the LLM
# await, so the connection is held only for ~10ms (the auth lookup) instead
# of the full 3-10s.
#
# Trade-off: the returned User is detached (expunged) from any session, so
# accessing relationships like `user.org` would fail with DetachedInstanceError.
# Callers must use only scalar attributes (id, name, phone, user_type,
# organization_id, area_name, is_active). LLM endpoints already only need
# `user.id` for cost attribution, so this is fine for them.
# ---------------------------------------------------------------------------


def get_current_user_lite(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Same auth as get_current_user but doesn't hold a request-scoped DB session.

    Use on long-running endpoints (LLM, anything awaiting an external service
    for >100ms) so the DB connection is freed before the slow await.

    Returns a *detached* User — relationships (org, stories, etc.) are not
    accessible without a re-merge into a fresh session.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter(User.id == user_id, User.deleted_at.is_(None))
            .first()
        )
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
            )
        # Expunge so the returned object survives session.close() — relationships
        # become inaccessible but scalar attributes (id, name, organization_id,
        # ...) are populated in memory and stay valid.
        db.expunge(user)
        return user
    finally:
        db.close()
