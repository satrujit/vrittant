"""Core framework for Vrittant widget plugins."""
from .plugin import WidgetPlugin, register, REGISTRY
from .db_client import (
    get_engine,
    ensure_schema,
    write_snapshot,
    read_snapshot,
    read_latest_snapshot,
    list_today_snapshots,
    is_item_served,
    mark_item_served,
    write_run,
    today_ist,
)
from .dedup import content_hash, DedupStrategy
from .translate import translate_to_odia

__all__ = [
    "WidgetPlugin",
    "register",
    "REGISTRY",
    "get_engine",
    "ensure_schema",
    "write_snapshot",
    "read_snapshot",
    "read_latest_snapshot",
    "list_today_snapshots",
    "is_item_served",
    "mark_item_served",
    "write_run",
    "today_ist",
    "content_hash",
    "DedupStrategy",
    "translate_to_odia",
]
