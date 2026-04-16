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
from .models.layout_template import LayoutTemplate  # noqa: F401
from .models.voice_enrollment import VoiceEnrollment  # noqa: F401
from .routers import admin, auth, editions, files, layout_ai, layout_templates, news_articles, sarvam, speaker, stories, templates

try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass  # tables already exist (race between workers)

# Initialize Firebase Admin SDK for ID token verification
from .firebase_admin_setup import init_firebase
init_firebase()

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

app.include_router(admin.router)
app.include_router(admin.config_router)
app.include_router(editions.router)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(stories.router, prefix="/stories", tags=["stories"])
app.include_router(files.router, prefix="/files", tags=["files"])
app.include_router(sarvam.router, tags=["sarvam"])
app.include_router(templates.router)
app.include_router(layout_templates.router)
app.include_router(layout_ai.router)
app.include_router(news_articles.router)
app.include_router(speaker.router, tags=["speaker"])

@app.get("/health")
def health():
    return {"status": "ok"}

# Seed users on startup
def seed_data():
    from .database import SessionLocal
    from .models.user import User, Entitlement
    from .models.organization import Organization
    db = SessionLocal()
    try:
        if db.query(Organization).count() == 0:
            # ── Organizations ──
            orgs = [
                Organization(
                    id="org-pragativadi",
                    name="Pragativadi",
                    slug="pragativadi",
                    logo_url="/uploads/org-logos/pragativadi.png",
                    theme_color="#FA6C38",
                ),
                Organization(
                    id="org-sambad",
                    name="Sambad",
                    slug="sambad",
                    logo_url="/uploads/org-logos/sambad.jpg",
                    theme_color="#1A1A1A",
                ),
                Organization(
                    id="org-prajaspoorthi",
                    name="Prajaspoorthi",
                    slug="prajaspoorthi",
                    logo_url="/uploads/org-logos/prajaspoorthi.png",
                    theme_color="#2A2A8E",
                ),
            ]
            db.add_all(orgs)
            db.flush()

            page_keys = ["dashboard", "stories", "review", "editions", "reporters", "social_export", "news_feed"]

            # ── Pragativadi users ──
            prag_reporter = User(
                name="Satrujit Mohapatra",
                phone="+917008660295",
                area_name="ନୟାଗଡ଼",
                organization="Pragativadi",
                organization_id="org-pragativadi",
                user_type="reporter",
            )
            db.add(prag_reporter)

            prag_reviewer1 = User(
                name="Editor Reviewer",
                phone="+918984336534",
                user_type="org_admin",
                organization="Pragativadi",
                organization_id="org-pragativadi",
            )
            db.add(prag_reviewer1)

            prag_reviewer2 = User(
                name="Aishwarya",
                phone="+918280103897",
                user_type="reviewer",
                organization="Pragativadi",
                organization_id="org-pragativadi",
            )
            db.add(prag_reviewer2)
            db.flush()

            for u in [prag_reviewer1, prag_reviewer2]:
                for key in page_keys:
                    db.add(Entitlement(user_id=u.id, page_key=key))

            # ── Sambad users ──
            sambad_reporter1 = User(
                name="Rajesh Panda",
                phone="+919000000101",
                area_name="ଭୁବନେଶ୍ୱର",
                organization="Sambad",
                organization_id="org-sambad",
                user_type="reporter",
            )
            sambad_reporter2 = User(
                name="Priyanka Sahoo",
                phone="+919000000102",
                area_name="କଟକ",
                organization="Sambad",
                organization_id="org-sambad",
                user_type="reporter",
            )
            sambad_reviewer = User(
                name="Sambad Editor",
                phone="+919000000103",
                user_type="org_admin",
                organization="Sambad",
                organization_id="org-sambad",
            )
            db.add_all([sambad_reporter1, sambad_reporter2, sambad_reviewer])
            db.flush()

            for key in page_keys:
                db.add(Entitlement(user_id=sambad_reviewer.id, page_key=key))

            # ── Prajaspoorthi users ──
            praja_reporter1 = User(
                name="Venkat Reddy",
                phone="+919000000201",
                area_name="Hyderabad",
                organization="Prajaspoorthi",
                organization_id="org-prajaspoorthi",
                user_type="reporter",
            )
            praja_reporter2 = User(
                name="Lakshmi Devi",
                phone="+919000000202",
                area_name="Vijayawada",
                organization="Prajaspoorthi",
                organization_id="org-prajaspoorthi",
                user_type="reporter",
            )
            praja_reviewer = User(
                name="Prajaspoorthi Editor",
                phone="+919000000203",
                user_type="org_admin",
                organization="Prajaspoorthi",
                organization_id="org-prajaspoorthi",
            )
            db.add_all([praja_reporter1, praja_reporter2, praja_reviewer])
            db.flush()

            for key in page_keys:
                db.add(Entitlement(user_id=praja_reviewer.id, page_key=key))

            db.commit()

        # ── Seed OrgConfig for each org ──
        from .models.org_config import (
            OrgConfig, DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
            DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
        )
        if db.query(OrgConfig).count() == 0:
            all_orgs = db.query(Organization).all()
            for org in all_orgs:
                db.add(OrgConfig(
                    organization_id=org.id,
                    categories=DEFAULT_CATEGORIES,
                    publication_types=DEFAULT_PUBLICATION_TYPES,
                    page_suggestions=DEFAULT_PAGE_SUGGESTIONS,
                    priority_levels=DEFAULT_PRIORITY_LEVELS,
                    default_language="odia",
                ))
            db.commit()
    finally:
        db.close()

if settings.ENV != "prod":
    seed_data()
