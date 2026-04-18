import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .config import settings
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

@app.get("/health")
def health():
    return {"status": "ok"}

# Seed users on startup (dev only)
if settings.ENV != "prod":
    from .scripts.seed_dev import seed_data
    seed_data()
