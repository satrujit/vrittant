import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, engine
from .models.story_revision import StoryRevision  # noqa: F401 — ensure table is created
from .models.page_template import PageTemplate  # noqa: F401
from .routers import admin, auth, editions, files, layout_ai, sarvam, stories, templates

Base.metadata.create_all(bind=engine)

# Initialize Firebase Admin SDK for ID token verification
from .firebase_admin_setup import init_firebase
init_firebase()

app = FastAPI(title="Vrittant API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files as static assets (local dev only)
if settings.STORAGE_BACKEND == "local":
    _uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(_uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")

app.include_router(admin.router)
app.include_router(editions.router)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(stories.router, prefix="/stories", tags=["stories"])
app.include_router(files.router, prefix="/files", tags=["files"])
app.include_router(sarvam.router, tags=["sarvam"])
app.include_router(templates.router)
app.include_router(layout_ai.router)

@app.get("/health")
def health():
    return {"status": "ok"}

# Seed users on startup
def seed_data():
    from .database import SessionLocal
    from .models.user import User, Entitlement
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            # Reporter
            reporter = User(
                name="Satrujit Mohapatra",
                phone="+917008660295",
                area_name="ନୟାଗଡ଼",
                organization="Pragativadi",
                user_type="reporter",
            )
            db.add(reporter)

            # Reviewer
            reviewer = User(
                name="Editor Reviewer",
                phone="+918984336534",
                user_type="reviewer",
                organization="Pragativadi",
            )
            db.add(reviewer)
            db.flush()  # flush to get reviewer.id for entitlements

            # Entitlements for the reviewer
            page_keys = ["dashboard", "stories", "review", "editions", "reporters", "social_export"]
            for key in page_keys:
                db.add(Entitlement(user_id=reviewer.id, page_key=key))

            db.commit()
    finally:
        db.close()

seed_data()
