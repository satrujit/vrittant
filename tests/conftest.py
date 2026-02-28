import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from jose import jwt

from app.database import Base, get_db
from app.config import settings
from app.main import app
from app.models.user import User
from app.models.story import Story


@pytest.fixture()
def db():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    """TestClient that uses the test database."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def reviewer(db):
    """Create and return a reviewer user."""
    user = User(
        id="reviewer-1",
        name="Test Reviewer",
        phone="+911111111111",
        user_type="reviewer",
        organization="Test Org",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def reporter(db):
    """Create and return a reporter user."""
    user = User(
        id="reporter-1",
        name="Test Reporter",
        phone="+912222222222",
        user_type="reporter",
        area_name="Test Area",
        organization="Test Org",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def sample_story(db, reporter):
    """Create and return a submitted story."""
    story = Story(
        id="story-1",
        reporter_id=reporter.id,
        headline="Original Headline",
        category="politics",
        paragraphs=[{"id": "p1", "text": "Original paragraph one."}, {"id": "p2", "text": "Original paragraph two."}],
        status="submitted",
    )
    db.add(story)
    db.commit()
    return story


@pytest.fixture()
def auth_header(reviewer):
    """JWT Authorization header for the reviewer."""
    token = jwt.encode({"sub": reviewer.id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}
