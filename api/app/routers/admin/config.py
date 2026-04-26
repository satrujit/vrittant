"""Org-config endpoints.

`/admin/config` (GET, PUT) is mounted on the admin router (org_admin only).
`/config/me` is mounted on the separate config_router (any authed user)."""
from fastapi import Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import get_current_org_id, get_current_user, require_org_admin
from ...models.org_config import OrgConfig
from ...models.user import User
from ...schemas.org_admin import OrgConfigResponse, UpdateOrgConfigRequest
from . import config_router, router


# ---------------------------------------------------------------------------
# GET /admin/config  (org_admin only)
# ---------------------------------------------------------------------------
@router.get("/config", response_model=OrgConfigResponse)
def get_org_config(
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    config = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    if not config:
        from ...models.org_config import (
            DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
            DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
        )
        config = OrgConfig(
            organization_id=org_id,
            categories=DEFAULT_CATEGORIES,
            publication_types=DEFAULT_PUBLICATION_TYPES,
            page_suggestions=DEFAULT_PAGE_SUGGESTIONS,
            priority_levels=DEFAULT_PRIORITY_LEVELS,
            default_language="odia",
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


# ---------------------------------------------------------------------------
# PUT /admin/config  (org_admin only)
# ---------------------------------------------------------------------------
@router.put("/config", response_model=OrgConfigResponse)
def update_org_config(
    body: UpdateOrgConfigRequest,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    config = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    if not config:
        config = OrgConfig(organization_id=org_id)
        db.add(config)
    if body.categories is not None:
        config.categories = [c.model_dump() for c in body.categories]
    if body.publication_types is not None:
        config.publication_types = [p.model_dump() for p in body.publication_types]
    if body.page_suggestions is not None:
        config.page_suggestions = [p.model_dump() for p in body.page_suggestions]
    if body.priority_levels is not None:
        config.priority_levels = [p.model_dump() for p in body.priority_levels]
    if body.edition_names is not None:
        # Strip and de-dupe so the auto-seeder doesn't churn on
        # whitespace-only or repeated names if an admin pastes sloppily.
        seen = set()
        cleaned = []
        for raw in body.edition_names:
            name = (raw or "").strip()
            if name and name not in seen:
                seen.add(name)
                cleaned.append(name)
        config.edition_names = cleaned
    if body.email_forwarders is not None:
        # Lower-case + strip + de-dupe. Email comparison is
        # case-insensitive in practice; keeping a single canonical form
        # prevents "Pragativadi@Gmail.com" from accidentally bypassing
        # the allowlist when the same gateway forwards in lower-case.
        seen = set()
        cleaned = []
        for raw in body.email_forwarders:
            addr = (raw or "").strip().lower()
            if addr and "@" in addr and addr not in seen:
                seen.add(addr)
                cleaned.append(addr)
        config.email_forwarders = cleaned
    if body.whitelisted_contributors is not None:
        # Same lower-case + dedupe rule applied per-entry email. Empty
        # name is allowed (gets backfilled on first matched email).
        seen = set()
        cleaned = []
        for entry in body.whitelisted_contributors:
            email = (entry.email or "").strip().lower()
            if not email or "@" not in email or email in seen:
                continue
            seen.add(email)
            cleaned.append({
                "email": email,
                "name": (entry.name or "").strip(),
            })
        config.whitelisted_contributors = cleaned
    if body.default_language is not None:
        config.default_language = body.default_language
    db.commit()
    db.refresh(config)
    return config


# ---------------------------------------------------------------------------
# GET /config/me  (any authenticated user)
# ---------------------------------------------------------------------------
@config_router.get("/me", response_model=OrgConfigResponse)
def get_my_org_config(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
):
    config = db.query(OrgConfig).filter(OrgConfig.organization_id == org_id).first()
    if not config:
        from ...models.org_config import (
            DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
            DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
        )
        config = OrgConfig(
            organization_id=org_id,
            categories=DEFAULT_CATEGORIES,
            publication_types=DEFAULT_PUBLICATION_TYPES,
            page_suggestions=DEFAULT_PAGE_SUGGESTIONS,
            priority_levels=DEFAULT_PRIORITY_LEVELS,
            default_language="odia",
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config
