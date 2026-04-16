"""CRUD for organization-scoped HTML layout templates."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_reviewer, get_current_org_id
from ..utils.tz import now_ist
from ..models.layout_template import LayoutTemplate
from ..models.user import User

router = APIRouter(prefix="/admin/layout-templates", tags=["layout-templates"])


# ── Schemas ────────────────────────────────────────────────────────────────


class LayoutTemplateCreate(BaseModel):
    name: str
    mode: str = "flexible"
    html_content: str
    category: str | None = None
    thumbnail_url: str | None = None


class LayoutTemplateUpdate(BaseModel):
    name: Optional[str] = None
    mode: Optional[str] = None
    html_content: Optional[str] = None
    category: Optional[str] = None
    thumbnail_url: Optional[str] = None


class LayoutTemplateResponse(BaseModel):
    id: str
    name: str
    mode: str
    html_content: str
    category: str | None = None
    thumbnail_url: str | None = None
    organization_id: str
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LayoutTemplateSummary(BaseModel):
    """Lightweight list response — excludes html_content."""

    id: str
    name: str
    mode: str
    category: str | None = None
    thumbnail_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("", response_model=LayoutTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_layout_template(
    body: LayoutTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    if body.mode not in ("fixed", "flexible"):
        raise HTTPException(status_code=422, detail="mode must be 'fixed' or 'flexible'")

    tpl = LayoutTemplate(
        name=body.name,
        mode=body.mode,
        html_content=body.html_content,
        category=body.category,
        thumbnail_url=body.thumbnail_url,
        created_by=current_user.id,
        organization_id=org_id,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.get("", response_model=list[LayoutTemplateSummary])
def list_layout_templates(
    category: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    q = db.query(LayoutTemplate).filter(LayoutTemplate.organization_id == org_id)
    if category:
        q = q.filter(LayoutTemplate.category == category)
    return q.order_by(LayoutTemplate.updated_at.desc()).all()


@router.get("/{template_id}", response_model=LayoutTemplateResponse)
def get_layout_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    tpl = (
        db.query(LayoutTemplate)
        .filter(LayoutTemplate.id == template_id, LayoutTemplate.organization_id == org_id)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout template not found")
    return tpl


@router.put("/{template_id}", response_model=LayoutTemplateResponse)
def update_layout_template(
    template_id: str,
    body: LayoutTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    tpl = (
        db.query(LayoutTemplate)
        .filter(LayoutTemplate.id == template_id, LayoutTemplate.organization_id == org_id)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout template not found")

    if body.name is not None:
        tpl.name = body.name
    if body.mode is not None:
        if body.mode not in ("fixed", "flexible"):
            raise HTTPException(status_code=422, detail="mode must be 'fixed' or 'flexible'")
        tpl.mode = body.mode
    if body.html_content is not None:
        tpl.html_content = body.html_content
    if body.category is not None:
        tpl.category = body.category
    if body.thumbnail_url is not None:
        tpl.thumbnail_url = body.thumbnail_url

    tpl.updated_at = now_ist()
    db.commit()
    db.refresh(tpl)
    return tpl


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_layout_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    tpl = (
        db.query(LayoutTemplate)
        .filter(LayoutTemplate.id == template_id, LayoutTemplate.organization_id == org_id)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layout template not found")
    db.delete(tpl)
    db.commit()
