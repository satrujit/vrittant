"""Dedup strategies and helpers."""
from __future__ import annotations

import hashlib
import json
from enum import Enum


class DedupStrategy(str, Enum):
    NONE = "none"
    DETERMINISTIC = "deterministic"          # always serve the same content for a given key (e.g. today's date)
    UNIQUE_WITHIN_DAYS = "unique_within_days"
    UNIQUE_FOREVER = "unique_forever"


def content_hash(payload: dict | str) -> str:
    """Stable SHA-256 hex digest of payload."""
    if isinstance(payload, str):
        s = payload
    else:
        s = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
