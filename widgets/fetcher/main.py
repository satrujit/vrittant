"""Cloud Run Job entrypoint — daily widget fetcher.

Triggered by Cloud Scheduler at 00:30 IST. Discovers all registered plugins,
fetches them in parallel, dedups, translates, renders HTML, and writes
snapshots to Firestore.

Exits 0 unless every single plugin fails (so a transient API outage in one
widget doesn't fail the whole job).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Make repo root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jinja2 import Environment, FileSystemLoader, select_autoescape

from widgets_core import (
    REGISTRY,
    DedupStrategy,
    WidgetPlugin,
    ensure_schema,
    is_item_served,
    mark_item_served,
    write_run,
    write_snapshot,
)
from widgets_core.plugin import discover_plugins
from widgets_core.translate import translate_fields

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("widget-fetcher")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
JINJA = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=False,
)


async def run_one(plugin_cls: type[WidgetPlugin]) -> tuple[str, str, str | None]:
    """Run a single plugin → (widget_id, status, error_message)."""
    plugin = plugin_cls()
    wid = plugin.id
    try:
        # 1. fetch with timeout + retry
        last_exc: Exception | None = None
        payload: dict | None = None
        for attempt in range(plugin.max_retries + 1):
            try:
                payload = await asyncio.wait_for(plugin.fetch(), timeout=plugin.timeout_seconds)
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("[%s] fetch attempt %d failed: %s", wid, attempt + 1, exc)
        if payload is None:
            raise last_exc or RuntimeError("fetch returned None")

        # 2. dedup
        strategy = plugin.dedup_strategy
        key = plugin.dedup_key(payload) if strategy != DedupStrategy.NONE else None
        if key and strategy == DedupStrategy.UNIQUE_FOREVER and is_item_served(wid, key):
            return wid, "dedup_skipped", "already served forever"
        if (
            key
            and strategy == DedupStrategy.UNIQUE_WITHIN_DAYS
            and is_item_served(wid, key, within_days=plugin.dedup_window_days)
        ):
            return wid, "dedup_skipped", f"served within {plugin.dedup_window_days}d"

        # 3. translate
        if plugin.translate_fields:
            payload = await translate_fields(
                payload, plugin.translate_fields, context=plugin.category
            )

        # 4. render to HTML
        try:
            tpl = JINJA.get_template(plugin.template)
            html = tpl.render(
                widget_id=wid,
                title_en=plugin.title_en,
                title_or=plugin.title_or,
                category=plugin.category,
                source_name=plugin.source_name,
                source_url=plugin.source_url,
                data=payload,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("[%s] render failed", wid)
            raise

        # 5. write snapshot + mark served
        write_snapshot(wid, payload, html)
        if key and strategy in (DedupStrategy.UNIQUE_FOREVER, DedupStrategy.UNIQUE_WITHIN_DAYS):
            mark_item_served(wid, key)

        return wid, "ok", None

    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] FAILED", wid)
        return wid, "failed", str(exc)


async def main() -> int:
    ensure_schema()  # idempotent: creates widgets schema + tables on first run
    discover_plugins("plugins")
    if not REGISTRY:
        logger.error("No plugins discovered. Aborting.")
        return 2

    enabled = [cls for cls in REGISTRY.values() if cls.enabled]
    logger.info("Running %d plugin(s): %s", len(enabled), [c.id for c in enabled])

    results = await asyncio.gather(*(run_one(c) for c in enabled))
    summary = {wid: {"status": status, "error": err} for wid, status, err in results}

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    write_run(run_id, summary)

    ok = sum(1 for _, s, _ in results if s == "ok")
    skipped = sum(1 for _, s, _ in results if s == "dedup_skipped")
    failed = sum(1 for _, s, _ in results if s == "failed")
    logger.info("DONE — ok=%d skipped=%d failed=%d (run=%s)", ok, skipped, failed, run_id)

    # Only exit non-zero if every plugin failed
    return 1 if failed == len(enabled) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
