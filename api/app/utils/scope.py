"""Org-scoping helper for ORM lookups.

This module exists to centralize the "fetch by id, filter by organization,
or 404" pattern that was previously inlined across dozens of routers. One
of those inlined copies forgot the organization filter, which created the
cross-org IDOR class fixed in commit 289820a (a reviewer in org A could
reference stories owned by org B by guessing UUIDs).

Routers should always go through ``get_owned_or_404`` instead of writing
the manual ``.filter(Model.id == x).first()`` + None-check by hand, so the
org filter can never be silently dropped again.
"""

from typing import Type, TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

T = TypeVar("T")


def get_owned_or_404(db: Session, model: Type[T], obj_id, org_id: str) -> T:
    """Fetch a single row of ``model`` scoped to the caller's organization.

    Filters by both ``model.id == obj_id`` AND ``model.organization_id == org_id``
    in a single query, returning the row if it exists.

    Raises ``HTTPException(404)`` in two cases:
      1. No row with that id exists at all.
      2. A row exists, but it belongs to a different organization.

    The 404 on org-mismatch is deliberate — we do NOT return 403 here, because
    distinguishing "doesn't exist" from "exists but not yours" would let a
    caller probe whether arbitrary ids belong to other orgs. Same response
    shape for both cases means existence cannot be leaked.
    """
    obj = (
        db.query(model)
        .filter(model.id == obj_id, model.organization_id == org_id)
        .first()
    )
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj
