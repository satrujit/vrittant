"""PostgreSQL storage layer for widget snapshots and dedup ledger.

Reuses the existing ``vrittant-db`` Cloud SQL instance. All widget tables
live in a dedicated ``widgets`` schema so they're isolated from the main
application's tables and can be dropped wholesale without risk.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./widgets-local.db")
SCHEMA = os.getenv("WIDGET_SCHEMA", "widgets")

_IST = timezone(timedelta(hours=5, minutes=30))


# ── Engine (singleton) ────────────────────────────────────────────────────
_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        connect_args: dict[str, Any] = {}
        pool_kwargs: dict[str, Any] = {}
        if not DATABASE_URL.startswith("sqlite"):
            connect_args = {
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            }
            pool_kwargs = {
                "pool_size": 2,
                "max_overflow": 1,
                "pool_pre_ping": True,
                "pool_recycle": 300,
            }
        _engine = create_engine(DATABASE_URL, connect_args=connect_args, **pool_kwargs)
    return _engine


def today_ist() -> str:
    return datetime.now(_IST).strftime("%Y-%m-%d")


# ── Schema bootstrap (idempotent) ─────────────────────────────────────────
DDL = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA};

CREATE TABLE IF NOT EXISTS {SCHEMA}.snapshots (
    widget_id     TEXT        NOT NULL,
    date          DATE        NOT NULL,
    payload       JSONB       NOT NULL,
    rendered_html TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (widget_id, date)
);
CREATE INDEX IF NOT EXISTS snapshots_date_idx
    ON {SCHEMA}.snapshots (date DESC);

CREATE TABLE IF NOT EXISTS {SCHEMA}.served_items (
    widget_id    TEXT        NOT NULL,
    content_key  TEXT        NOT NULL,
    served_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (widget_id, content_key)
);
CREATE INDEX IF NOT EXISTS served_items_widget_served_idx
    ON {SCHEMA}.served_items (widget_id, served_at DESC);

CREATE TABLE IF NOT EXISTS {SCHEMA}.runs (
    run_id      TEXT        PRIMARY KEY,
    finished_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    results     JSONB       NOT NULL
);
"""


def ensure_schema() -> None:
    """Create schema and tables if missing. Safe to call repeatedly."""
    eng = get_engine()
    if eng.dialect.name == "sqlite":
        # Minimal sqlite-friendly DDL for local dev
        with eng.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    widget_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    rendered_html TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (widget_id, date)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS served_items (
                    widget_id TEXT NOT NULL,
                    content_key TEXT NOT NULL,
                    served_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (widget_id, content_key)
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    finished_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    results TEXT NOT NULL
                )
            """))
        return

    with eng.begin() as conn:
        for stmt in [s.strip() for s in DDL.split(";") if s.strip()]:
            conn.execute(text(stmt))


# ── Snapshot CRUD ─────────────────────────────────────────────────────────
def write_snapshot(
    widget_id: str,
    payload: dict,
    rendered_html: str,
    *,
    date: str | None = None,
) -> None:
    eng = get_engine()
    d = date or today_ist()
    if eng.dialect.name == "sqlite":
        sql = text("""
            INSERT INTO snapshots (widget_id, date, payload, rendered_html)
            VALUES (:wid, :d, :payload, :html)
            ON CONFLICT (widget_id, date) DO UPDATE SET
              payload = excluded.payload,
              rendered_html = excluded.rendered_html
        """)
        with eng.begin() as conn:
            conn.execute(sql, {"wid": widget_id, "d": d, "payload": json.dumps(payload, default=str), "html": rendered_html})
        return
    sql = text(f"""
        INSERT INTO {SCHEMA}.snapshots (widget_id, date, payload, rendered_html)
        VALUES (:wid, :d, CAST(:payload AS JSONB), :html)
        ON CONFLICT (widget_id, date) DO UPDATE SET
          payload       = EXCLUDED.payload,
          rendered_html = EXCLUDED.rendered_html,
          created_at    = NOW()
    """)
    with eng.begin() as conn:
        conn.execute(sql, {"wid": widget_id, "d": d, "payload": json.dumps(payload, default=str), "html": rendered_html})


def _row_to_snapshot(row) -> dict:
    payload = row.payload
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {
        "widget_id": row.widget_id,
        "date": str(row.date),
        "payload": payload,
        "rendered_html": row.rendered_html,
    }


def read_snapshot(widget_id: str, date: str | None = None) -> dict | None:
    eng = get_engine()
    d = date or today_ist()
    table = "snapshots" if eng.dialect.name == "sqlite" else f"{SCHEMA}.snapshots"
    sql = text(f"SELECT widget_id, date, payload, rendered_html FROM {table} WHERE widget_id=:w AND date=:d")
    with eng.connect() as conn:
        row = conn.execute(sql, {"w": widget_id, "d": d}).first()
    return _row_to_snapshot(row) if row else None


def read_latest_snapshot(widget_id: str, max_age_days: int = 7) -> dict | None:
    eng = get_engine()
    table = "snapshots" if eng.dialect.name == "sqlite" else f"{SCHEMA}.snapshots"
    sql = text(f"""
        SELECT widget_id, date, payload, rendered_html
        FROM {table}
        WHERE widget_id = :w AND date >= :cutoff
        ORDER BY date DESC
        LIMIT 1
    """)
    cutoff = (datetime.now(_IST).date() - timedelta(days=max_age_days)).strftime("%Y-%m-%d")
    with eng.connect() as conn:
        row = conn.execute(sql, {"w": widget_id, "cutoff": cutoff}).first()
    return _row_to_snapshot(row) if row else None


def list_today_snapshots() -> list[dict]:
    eng = get_engine()
    table = "snapshots" if eng.dialect.name == "sqlite" else f"{SCHEMA}.snapshots"
    sql = text(f"SELECT widget_id, date, payload, rendered_html FROM {table} WHERE date=:d")
    with eng.connect() as conn:
        rows = conn.execute(sql, {"d": today_ist()}).all()
    return [_row_to_snapshot(r) for r in rows]


# ── Dedup ledger ──────────────────────────────────────────────────────────
def is_item_served(widget_id: str, content_key: str, *, within_days: int | None = None) -> bool:
    eng = get_engine()
    table = "served_items" if eng.dialect.name == "sqlite" else f"{SCHEMA}.served_items"
    if within_days is None:
        sql = text(f"SELECT 1 FROM {table} WHERE widget_id=:w AND content_key=:k LIMIT 1")
        with eng.connect() as conn:
            return conn.execute(sql, {"w": widget_id, "k": content_key}).first() is not None
    cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
    sql = text(f"SELECT 1 FROM {table} WHERE widget_id=:w AND content_key=:k AND served_at >= :cutoff LIMIT 1")
    with eng.connect() as conn:
        return conn.execute(sql, {"w": widget_id, "k": content_key, "cutoff": cutoff}).first() is not None


def mark_item_served(widget_id: str, content_key: str) -> None:
    eng = get_engine()
    if eng.dialect.name == "sqlite":
        sql = text("""
            INSERT INTO served_items (widget_id, content_key) VALUES (:w, :k)
            ON CONFLICT (widget_id, content_key) DO UPDATE SET served_at = CURRENT_TIMESTAMP
        """)
    else:
        sql = text(f"""
            INSERT INTO {SCHEMA}.served_items (widget_id, content_key) VALUES (:w, :k)
            ON CONFLICT (widget_id, content_key) DO UPDATE SET served_at = NOW()
        """)
    with eng.begin() as conn:
        conn.execute(sql, {"w": widget_id, "k": content_key})


# ── Run audit ─────────────────────────────────────────────────────────────
def write_run(run_id: str, results: dict) -> None:
    eng = get_engine()
    if eng.dialect.name == "sqlite":
        sql = text("INSERT INTO runs (run_id, results) VALUES (:r, :j)")
        with eng.begin() as conn:
            conn.execute(sql, {"r": run_id, "j": json.dumps(results, default=str)})
        return
    sql = text(f"INSERT INTO {SCHEMA}.runs (run_id, results) VALUES (:r, CAST(:j AS JSONB))")
    with eng.begin() as conn:
        conn.execute(sql, {"r": run_id, "j": json.dumps(results, default=str)})
