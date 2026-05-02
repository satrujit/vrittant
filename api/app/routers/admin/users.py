"""Admin user management endpoints (org_admin only)."""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import get_current_org_id, require_org_admin
from ...models.org_config import OrgConfig
from ...models.organization import Organization
from ...models.user import Entitlement, User
from ...services.assignment import redistribute_open_stories
from ...schemas.org_admin import (
    CreateUserRequest,
    UpdateUserEntitlementsRequest,
    UpdateUserRequest,
    UpdateUserRoleRequest,
    UserManagementResponse,
)
from ...utils.scope import get_owned_or_404
from . import router


def _user_response(user: User) -> UserManagementResponse:
    return UserManagementResponse(
        id=user.id, name=user.name, phone=user.phone, email=user.email,
        user_type=user.user_type, area_name=user.area_name, is_active=user.is_active,
        entitlements=[e.page_key for e in user.entitlements],
        categories=list(user.categories or []),
        regions=list(user.regions or []),
    )


def _validate_categories(db: Session, org_id: str, categories: list[str]) -> None:
    if not categories:
        return
    cfg = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    allowed: set[str] = set()
    if cfg and cfg.categories:
        for item in cfg.categories:
            key = item.get("key") if isinstance(item, dict) else None
            if key:
                allowed.add(key)
    for cat in categories:
        if cat not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown category: {cat}",
            )


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
    _validate_categories(db, org_id, body.categories)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    user = User(
        name=body.name, phone=body.phone, email=body.email, area_name=body.area_name,
        user_type=body.user_type, organization=org.name if org else "", organization_id=org_id,
        categories=list(body.categories), regions=list(body.regions),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_response(user)


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
    # Capture pre-mutation state to detect reviewer-deactivation triggers.
    was_active = user.is_active
    was_reviewer = user.user_type == "reviewer"
    if body.name is not None: user.name = body.name
    if body.email is not None: user.email = body.email
    if body.area_name is not None: user.area_name = body.area_name
    if body.is_active is not None: user.is_active = body.is_active
    if body.categories is not None:
        _validate_categories(db, org_id, body.categories)
        user.categories = list(body.categories)
    if body.regions is not None:
        user.regions = list(body.regions)
    db.flush()
    if was_active and was_reviewer and user.is_active is False:
        redistribute_open_stories(db, user, admin.id)
    db.commit()
    db.refresh(user)
    return _user_response(user)


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
    was_reviewer = user.user_type == "reviewer"
    user.user_type = body.user_type
    db.flush()
    if was_reviewer and user.user_type != "reviewer":
        redistribute_open_stories(db, user, admin.id)
    db.commit()
    db.refresh(user)
    return _user_response(user)


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
    # Belt + suspenders. get_owned_or_404 above already proved this user
    # belongs to org_id, so a delete-by-user_id alone is safe today. But
    # the Entitlement table has no organization_id of its own, and a
    # future refactor that drops the get_owned_or_404 call (or moves it)
    # would silently make this delete cross-org. Constrain the delete
    # to entitlements whose user is also in this org via subquery — if
    # the user moves orgs (we don't do that today, but...) the wrong-
    # org entitlements simply don't match and stay put.
    db.query(Entitlement).filter(
        Entitlement.user_id == user_id,
        Entitlement.user_id.in_(
            db.query(User.id).filter(User.organization_id == org_id)
        ),
    ).delete(synchronize_session=False)
    for key in body.page_keys:
        db.add(Entitlement(user_id=user_id, page_key=key))
    db.commit()
    db.refresh(user)
    return _user_response(user)
