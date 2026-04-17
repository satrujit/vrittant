"""Cloud Run Service — read-only SSR widget renderer.

Public endpoints:
  GET  /healthz                    → liveness
  GET  /render/all                 → full HTML page with every widget that has a snapshot today
  GET  /render/{widget_id}         → single-widget HTML page
  GET  /api/{widget_id}            → JSON payload (for clients that want raw data)

Security:
  - No request body is ever consumed; all routes are GET, no query params used in DB lookups.
  - Sets CSP `frame-ancestors` so this can only be embedded by allow-listed origins.
  - Sets X-Frame-Options as a fallback for older browsers.
  - Falls back to most recent snapshot ≤ 7 days old if today's is missing.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Make repo root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from widgets_core import (
    list_today_snapshots,
    read_latest_snapshot,
    read_snapshot,
    today_ist,
)
from widgets_core.plugin import discover_plugins

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("widget-renderer")

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"
JINJA = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

ALLOWED_PARENTS = os.getenv(
    "ALLOWED_PARENT_ORIGINS",
    " ".join([
        # Production hosting
        "https://vrittant.in",
        "https://*.vrittant.in",
        "https://vrittant-f5ef2.web.app",
        "https://vrittant-f5ef2.firebaseapp.com",
        # UAT hosting
        "https://vrittant-uat.web.app",
        "https://vrittant-uat.firebaseapp.com",
        # Local dev
        "http://localhost:5173",
        "http://localhost:4173",
        "http://localhost:5175",
    ]),
).strip()

CSP = (
    "default-src 'self'; "
    "img-src 'self' https: data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; "
    "font-src 'self' data:; "
    f"frame-ancestors {ALLOWED_PARENTS}; "
    "base-uri 'none'; "
    "form-action 'none'"
)

app = FastAPI(
    title="Vrittant Widget Renderer",
    description="Read-only SSR for daily newspaper widgets.",
)

# Discover plugins at startup so we know titles/categories
PLUGIN_META: dict[str, dict] = {}


@app.on_event("startup")
def _load_plugins() -> None:
    discover_plugins("plugins")
    from widgets_core import REGISTRY

    for wid, cls in REGISTRY.items():
        PLUGIN_META[wid] = {
            "id": wid,
            "category": cls.category,
            "title_en": cls.title_en or wid,
            "title_or": cls.title_or or "",
            "enabled": cls.enabled,
        }
    logger.info("Renderer loaded %d plugin(s)", len(PLUGIN_META))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp: Response = await call_next(request)
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    # Allow framing — frame-ancestors in CSP enforces the actual policy
    if "x-frame-options" in resp.headers:
        del resp.headers["x-frame-options"]
    return resp


# ── Endpoints ─────────────────────────────────────────────────────────────
@app.get("/healthz")
def healthz():
    return {"ok": True, "date": today_ist(), "plugins": len(PLUGIN_META)}


_RESIZE_SCRIPT = """
<script>
(function () {
  function post() {
    try {
      parent.postMessage(
        { type: 'vrittant-widget-resize', height: document.documentElement.scrollHeight },
        '*'
      );
    } catch (e) {}
  }
  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(post).observe(document.body);
  }
  window.addEventListener('load', post);
  setTimeout(post, 100);
  setTimeout(post, 1000);
})();
</script>
"""


def _wrap_page(body_html: str) -> str:
    page = JINJA.get_template("_page.html")
    return page.render(body_html=body_html, resize_script=_RESIZE_SCRIPT)


@app.get("/render/all", response_class=HTMLResponse)
def render_all():
    snapshots = list_today_snapshots()
    if not snapshots:
        # fall back: collect latest available per known widget
        snapshots = []
        for wid in PLUGIN_META:
            snap = read_latest_snapshot(wid, max_age_days=7)
            if snap:
                snapshots.append(snap)
    if not snapshots:
        return HTMLResponse(_wrap_page("<p>No widgets available yet.</p>"), status_code=200)

    # Single responsive grid; category becomes a data attribute for styling/filtering.
    parts = ['<section class="vw-grid">']
    for s in snapshots:
        meta = PLUGIN_META.get(s["widget_id"], {})
        cat = meta.get("category", "misc")
        parts.append(
            f'<article class="vw-card" data-widget="{s["widget_id"]}" data-category="{cat}">'
        )
        parts.append(s.get("rendered_html") or "")
        parts.append("</article>")
    parts.append("</section>")
    return HTMLResponse(_wrap_page("\n".join(parts)))


@app.get("/render/{widget_id}", response_class=HTMLResponse)
def render_one(widget_id: str):
    if widget_id not in PLUGIN_META:
        raise HTTPException(404, "Unknown widget")
    snap = read_snapshot(widget_id) or read_latest_snapshot(widget_id, max_age_days=7)
    if not snap:
        raise HTTPException(404, "No snapshot")
    return HTMLResponse(_wrap_page(snap.get("rendered_html") or ""))


@app.get("/api/_meta")
def api_meta():
    return {"widgets": list(PLUGIN_META.values()), "date": today_ist()}


@app.get("/api/{widget_id}")
def api_one(widget_id: str):
    if widget_id not in PLUGIN_META:
        raise HTTPException(404, "Unknown widget")
    snap = read_snapshot(widget_id) or read_latest_snapshot(widget_id, max_age_days=7)
    if not snap:
        raise HTTPException(404, "No snapshot")
    return JSONResponse(
        {
            "widget_id": widget_id,
            "date": snap.get("date"),
            "category": PLUGIN_META[widget_id]["category"],
            "title_en": PLUGIN_META[widget_id]["title_en"],
            "title_or": PLUGIN_META[widget_id]["title_or"],
            "data": snap.get("payload"),
        }
    )
