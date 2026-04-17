"""Admin user management endpoints (org_admin only)."""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import get_current_org_id, require_org_admin
from ...models.organization import Organization
from ...models.user import Entitlement, User
from ...schemas.org_admin import (
    CreateUserRequest,
    UpdateUserEntitlementsRequest,
    UpdateUserRequest,
    UpdateUserRoleRequest,
    UserManagementResponse,
)
from ...utils.scope import get_owned_or_404
from . import router


# ---------------------------------------------------------------------------
# POST /admin/users  (org_admin only)
# ---------------------------------------------------------------------------
@router.post("/users", response_model=UserManagementResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    existing = db.query(User).filter(User.phone == body.phone).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")
    org = db.query(Organization).filter(Organization.id == org_id).first()
    user = User(
        name=body.name, phone=body.phone, email=body.email, area_name=body.area_name,
        user_type=body.user_type, organization=org.name if org else "", organization_id=org_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserManagementResponse(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        user_type=user.user_type, area_name=user.area_name, is_active=user.is_active,
        entitlements=[e.page_key for e in user.entitlements],
    )


# ---------------------------------------------------------------------------
# PUT /admin/users/{user_id}  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/users/{user_id}", response_model=UserManagementResponse)
def update_user(
    user_id: str, body: UpdateUserRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    user = get_owned_or_404(db, User, user_id, org_id)
    if body.name is not None: user.name = body.name
    if body.email is not None: user.email = body.email
    if body.area_name is not None: user.area_name = body.area_name
    if body.is_active is not None: user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return UserManagementResponse(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        user_type=user.user_type, area_name=user.area_name, is_active=user.is_active,
        entitlements=[e.page_key for e in user.entitlements],
    )


# ---------------------------------------------------------------------------
# PUT /admin/users/{user_id}/role  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/users/{user_id}/role", response_model=UserManagementResponse)
def update_user_role(
    user_id: str, body: UpdateUserRoleRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    user = get_owned_or_404(db, User, user_id, org_id)
    user.user_type = body.user_type
    db.commit()
    db.refresh(user)
    return UserManagementResponse(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        user_type=user.user_type, area_name=user.area_name, is_active=user.is_active,
        entitlements=[e.page_key for e in user.entitlements],
    )


# ---------------------------------------------------------------------------
# PUT /admin/users/{user_id}/entitlements  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/users/{user_id}/entitlements", response_model=UserManagementResponse)
def update_user_entitlements(
    user_id: str, body: UpdateUserEntitlementsRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    user = get_owned_or_404(db, User, user_id, org_id)
    db.query(Entitlement).filter(Entitlement.user_id == user_id).delete()
    for key in body.page_keys:
        db.add(Entitlement(user_id=user_id, page_key=key))
    db.commit()
    db.refresh(user)
    return UserManagementResponse(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        user_type=user.user_type, area_name=user.area_name, is_active=user.is_active,
        entitlements=[e.page_key for e in user.entitlements],
    )
