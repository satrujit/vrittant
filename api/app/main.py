import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .config import settings

# ---------------------------------------------------------------------------
# Sentry — error tracking + performance monitoring
# ---------------------------------------------------------------------------
# Empty DSN = no-op (dev/local/UAT without a DSN configured).
# In production, set SENTRY_DSN in the .env file.
if settings.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        traces_sample_rate=0.1,        # 10% of requests get performance traces
        profiles_sample_rate=0.1,      # profile 10% of traced requests
        send_default_pii=False,        # don't send PII (phone numbers, etc.)
        enable_tracing=True,
    )


# ---------------------------------------------------------------------------
# Logging level
# ---------------------------------------------------------------------------
# Setting `logging.getLogger("app").setLevel(INFO)` alone wasn't enough
# in prod — gunicorn owns the root logger config and its handler
# filters above WARNING by default, so even with our logger at INFO
# the records were dropped at the root handler. We attach our own
# StreamHandler directly to the "app" logger and disable propagation
# so app log lines bypass gunicorn's filter and write to stdout
# (which Cloud Run scoops up and ships to Cloud Logging).
#
# This means the STT proxy's INFO lines (session start, Sarvam
# reconnect, session end) actually reach Cloud Logging, which is
# what made the difference between "we have observability" and "we
# fly blind whenever a reporter complains about no-transcript".
import sys
_app_logger = logging.getLogger("app")
_app_logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.StreamHandler) for h in _app_logger.handlers):
    _h = logging.StreamHandler(sys.stdout)
    _h.setLevel(logging.INFO)
    _h.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )
    _app_logger.addHandler(_h)
# Don't double-emit via root (avoids gunicorn's handler dropping it AND
# preventing duplicate lines if root somehow does pass it through).
_app_logger.propagate = False
from .database import Base, engine
from .models.story_revision import StoryRevision  # noqa: F401 — ensure table is created
from .models.page_template import PageTemplate  # noqa: F401
from .models.org_config import OrgConfig  # noqa: F401
from .models.news_article import NewsArticle  # noqa: F401
from .models.voice_enrollment import VoiceEnrollment  # noqa: F401
from .models.webhook_dedup import WhatsappInboundDedup  # noqa: F401
from .routers import ROUTERS

try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass  # tables already exist (race between workers)

docs_kwargs = {}
if settings.ENV == "prod":
    docs_kwargs = {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="Vrittant API", version="0.3.0", **docs_kwargs)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)


# Transient-DB-error retry middleware, scoped to /webhooks/whatsapp/* only.
# Webhooks are idempotent at the Gupshup boundary (whatsapp_inbound_dedup
# keys on message_id) so a same-request replay is safe. Other routes are
# NOT idempotent and are intentionally not wrapped — a retry on a
# non-idempotent endpoint risks double side-effects.
from .services.whatsapp.reliability import retry_on_transient_db_errors
from .services.whatsapp.auth import signature_check_middleware


# IMPORTANT: middleware registration order is "last registered = innermost".
# We register the retry wrapper FIRST (innermost) so the retry only fires
# for requests that have already passed signature verification — otherwise
# we'd burn retries on unauthenticated payloads.
@app.middleware("http")
async def _whatsapp_retry_wrapper(request: Request, call_next):
    if request.url.path.startswith("/webhooks/whatsapp"):
        return await retry_on_transient_db_errors(request, call_next)
    return await call_next(request)


# Signature check registered SECOND (outermost). Runs first; rejects
# unauthenticated webhook payloads with 403 before they reach the
# router or the retry wrapper.
@app.middleware("http")
async def _whatsapp_signature_check(request: Request, call_next):
    return await signature_check_middleware(request, call_next)


@app.on_event("startup")
def warm_db_pool():
    """Warm the database connection pool and ensure pg_trgm extension exists."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        from .database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            # Ensure pg_trgm is available for fuzzy search
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.commit()
        logger.info("Database connection pool warmed, pg_trgm enabled")
    except Exception as e:
        logger.warning("Failed to warm DB pool (will retry on first request): %s", e)


@app.on_event("startup")
async def start_prompt_sender():
    """Launch the WhatsApp prompt-sender background loop."""
    import asyncio
    from .services.whatsapp.dispatcher import prompt_sender_loop
    asyncio.create_task(prompt_sender_loop())

# Serve uploaded files locally in dev; in prod GCS URLs are returned directly
if settings.STORAGE_BACKEND == "local":
    _uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(_uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")

for router, prefix, tags in ROUTERS:
    kwargs = {}
    if prefix:
        kwargs["prefix"] = prefix
    if tags:
        kwargs["tags"] = tags
    app.include_router(router, **kwargs)

@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}

# Seed users on startup (dev only)
if settings.ENV != "prod":
    from .scripts.seed_dev import seed_data
    seed_data()
