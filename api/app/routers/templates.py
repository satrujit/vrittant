from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_reviewer, get_current_org_id
from ..utils.tz import now_ist
from ..models.page_template import PageTemplate
from ..models.user import User

router = APIRouter(prefix="/admin/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    paper_size: str = "broadsheet"
    width_mm: float
    height_mm: float
    zones: list[dict]


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    paper_size: Optional[str] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    zones: Optional[list[dict]] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    paper_size: str
    width_mm: float
    height_mm: float
    zones: list[dict]
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    body: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    tpl = PageTemplate(
        name=body.name,
        paper_size=body.paper_size,
        width_mm=body.width_mm,
        height_mm=body.height_mm,
        zones=body.zones,
        created_by=current_user.id,
        organization_id=org_id,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.get("", response_model=list[TemplateResponse])
def list_templates(db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    return db.query(PageTemplate).filter(PageTemplate.organization_id == org_id).order_by(PageTemplate.updated_at.desc()).all()


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(template_id: str, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    tpl = db.query(PageTemplate).filter(PageTemplate.id == template_id, PageTemplate.organization_id == org_id).first()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return tpl


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: str,
    body: TemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    tpl = db.query(PageTemplate).filter(PageTemplate.id == template_id, PageTemplate.organization_id == org_id).first()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if body.name is not None:
        tpl.name = body.name
    if body.paper_size is not None:
        tpl.paper_size = body.paper_size
    if body.width_mm is not None:
        tpl.width_mm = body.width_mm
    if body.height_mm is not None:
        tpl.height_mm = body.height_mm
    if body.zones is not None:
        tpl.zones = body.zones

    tpl.updated_at = now_ist()
    db.commit()
    db.refresh(tpl)
    return tpl


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: str, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    tpl = db.query(PageTemplate).filter(PageTemplate.id == template_id, PageTemplate.organization_id == org_id).first()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    db.delete(tpl)
    db.commit()
