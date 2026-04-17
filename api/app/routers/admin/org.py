"""Admin organization-management endpoints (org_admin only)."""
import os

from fastapi import Depends, File as FastAPIFile, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import get_current_org_id, require_org_admin
from ...models.organization import Organization
from ...models.user import User
from ...schemas.org_admin import OrgResponse, UpdateOrgRequest
from . import router


# ---------------------------------------------------------------------------
# PUT /admin/org  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/org", response_model=OrgResponse)
def update_org(
    body: UpdateOrgRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if body.name is not None: org.name = body.name
    if body.theme_color is not None: org.theme_color = body.theme_color
    db.commit()
    db.refresh(org)
    return org


# ---------------------------------------------------------------------------
# PUT /admin/org/logo  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/org/logo", response_model=OrgResponse)
async def update_org_logo(
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    from ...services.storage import save_logo
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed for logos")
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo file too large (max 5 MB)")
    org.logo_url = save_logo(contents, org.slug, ext)
    db.commit()
    db.refresh(org)
    return org
