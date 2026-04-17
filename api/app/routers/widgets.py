"""Widgets — read consolidated widget snapshots written by widget_data_fetcher.

Returns the latest payload per widget_id from `widgets.snapshots`. The React
reviewer panel calls `GET /api/widgets/all` and renders everything natively
(no iframe, no Jinja). Single endpoint, no auth — these are public newspaper
widgets.
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/widgets", tags=["widgets"])


@router.get("/all")
def get_all_widgets(db: Session = Depends(get_db)) -> dict:
    """Return the most recent snapshot per widget_id as a flat dict.

    Shape: { "as_of": "2026-04-17", "widgets": { "<id>": <payload>, ... } }
    """
    # DISTINCT ON gets the latest row per widget_id without a window function.
    rows = db.execute(text("""
        SELECT DISTINCT ON (widget_id) widget_id, date, payload
        FROM widgets.snapshots
        ORDER BY widget_id, date DESC
    """)).mappings().all()

    widgets: dict[str, dict] = {}
    latest_date: date | None = None
    for r in rows:
        widgets[r["widget_id"]] = r["payload"]
        if latest_date is None or r["date"] > latest_date:
            latest_date = r["date"]

    return {
        "as_of": latest_date.isoformat() if latest_date else None,
        "count": len(widgets),
        "widgets": widgets,
    }


@router.get("/{widget_id}")
def get_one_widget(widget_id: str, db: Session = Depends(get_db)) -> dict:
    """Return the single most recent snapshot for one widget_id."""
    row = db.execute(text("""
        SELECT widget_id, date, payload
        FROM widgets.snapshots
        WHERE widget_id = :wid
        ORDER BY date DESC
        LIMIT 1
    """), {"wid": widget_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail=f"No snapshot for widget '{widget_id}'")

    return {
        "id": row["widget_id"],
        "as_of": row["date"].isoformat(),
        "payload": row["payload"],
    }
