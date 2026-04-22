# Backend + Persistence + Bug Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix text duplication, build FastAPI backend with auth + story CRUD, wire Flutter app to backend for login, story persistence, and home screen.

**Architecture:** FastAPI backend (SQLite + SQLAlchemy) at `/Users/admin/Desktop/newsflow-api/`. Flutter app talks to backend via Dio HTTP client through a new `ApiService`. Auth via JWT with hardcoded OTP. Stories saved to server on every change.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, SQLite, python-jose (JWT) | Flutter 3.41, Riverpod 3.x, GoRouter, Dio, SharedPreferences

---

### Task 1: Fix Text Duplication Bug

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/features/create_news/providers/create_news_provider.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/core/services/streaming_stt_web.dart`

**Step 1: Update `_handleMessage` in streaming_stt_web.dart to distinguish partial vs final transcripts**

The Sarvam streaming API sends `type: 'data'` messages with cumulative partial transcripts within a VAD window. We need to emit structured data so the listener can tell partials apart from finals.

In `/Users/admin/Desktop/newsflow/lib/core/services/streaming_stt_web.dart`, change the `_transcriptController` from `StreamController<String>` to `StreamController<SttSegment>` and add a segment class:

```dart
/// A transcript segment from the streaming STT API.
class SttSegment {
  final String text;
  final bool isFinal; // true when VAD-end detected

  const SttSegment({required this.text, this.isFinal = false});
}
```

Update `_handleMessage` (around line 222) to:
- Emit `SttSegment(text: transcript, isFinal: false)` for `type: 'data'` messages
- Emit `SttSegment(text: lastTranscript, isFinal: true)` for `type: 'events'` with VAD-end signal
- Track `_lastPartialTranscript` to send as final when VAD ends

Update the `start()` return type to `Future<Stream<SttSegment>>`.

**Step 2: Update the transcript listener in create_news_provider.dart**

In `/Users/admin/Desktop/newsflow/lib/features/create_news/providers/create_news_provider.dart`, add a `String _committedTranscript = '';` field to `NotepadNotifier`.

Change the listener (around line 266) from appending to:

```dart
_transcriptSubscription = transcriptStream.listen(
  (segment) {
    if (segment.isFinal) {
      // Commit this segment and reset partial
      final separator = _committedTranscript.isEmpty ? '' : ' ';
      _committedTranscript = '$_committedTranscript$separator${segment.text}';
      state = state.copyWith(liveTranscript: _committedTranscript);
    } else {
      // Replace partial (cumulative within VAD window)
      final separator = _committedTranscript.isEmpty ? '' : ' ';
      state = state.copyWith(
        liveTranscript: '$_committedTranscript$separator${segment.text}',
      );
    }
  },
  // ... existing onError
);
```

Also reset `_committedTranscript = '';` in the START recording section (around line 257) and in `reset()`.

**Step 3: Verify the fix compiles**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web 2>&1 | tail -5
```

Expected: `✓ Built build/web` with no errors.

**Step 4: Commit**

```bash
cd /Users/admin/Desktop/newsflow && git add lib/core/services/streaming_stt_web.dart lib/features/create_news/providers/create_news_provider.dart && git commit -m "fix: resolve text duplication by distinguishing partial vs final STT transcripts"
```

---

### Task 2: Scaffold FastAPI Backend

**Files:**
- Create: `/Users/admin/Desktop/newsflow-api/requirements.txt`
- Create: `/Users/admin/Desktop/newsflow-api/app/__init__.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/main.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/config.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/database.py`

**Step 1: Create project structure and requirements**

```
newsflow-api/
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── reporter.py
│   │   └── story.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── story.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   └── stories.py
│   └── deps.py
```

`requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35
python-jose[cryptography]==3.3.0
passlib==1.7.4
python-multipart==0.0.9
pydantic-settings==2.5.0
```

`app/config.py`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./newsflow.db"
    SECRET_KEY: str = "newsflow-dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 30
    HARDCODED_OTP: str = "123456"

settings = Settings()
```

`app/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .routers import auth, stories

Base.metadata.create_all(bind=engine)

app = FastAPI(title="NewsFlow API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(stories.router, prefix="/stories", tags=["stories"])

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 2: Create venv and install deps**

```bash
cd /Users/admin/Desktop/newsflow-api && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

**Step 3: Verify server starts**

```bash
cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && uvicorn app.main:app --reload --port 8000 &
curl http://localhost:8000/health
# Expected: {"status":"ok"}
kill %1
```

**Step 4: Init git and commit**

```bash
cd /Users/admin/Desktop/newsflow-api && git init && echo -e "venv/\n__pycache__/\n*.db\n.env" > .gitignore && git add . && git commit -m "chore: scaffold FastAPI project with config and database"
```

---

### Task 3: Define Database Models

**Files:**
- Create: `/Users/admin/Desktop/newsflow-api/app/models/__init__.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/models/reporter.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/models/story.py`

**Step 1: Create Reporter model**

`app/models/reporter.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import relationship

from ..database import Base


class Reporter(Base):
    __tablename__ = "reporters"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    area_name = Column(String, nullable=False, default="")
    organization = Column(String, nullable=False, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    stories = relationship("Story", back_populates="reporter")
```

**Step 2: Create Story model**

`app/models/story.py`:
```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from ..database import Base


class Story(Base):
    __tablename__ = "stories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    reporter_id = Column(String, ForeignKey("reporters.id"), nullable=False, index=True)
    headline = Column(String, default="")
    category = Column(String, nullable=True)
    location = Column(String, nullable=True)
    paragraphs = Column(JSON, default=list)  # [{id, text, photo_path, created_at}]
    status = Column(String, default="draft")  # draft | submitted | approved | published | rejected
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    reporter = relationship("Reporter", back_populates="stories")
```

**Step 3: Create models __init__**

`app/models/__init__.py`:
```python
from .reporter import Reporter
from .story import Story

__all__ = ["Reporter", "Story"]
```

**Step 4: Commit**

```bash
cd /Users/admin/Desktop/newsflow-api && git add app/models/ && git commit -m "feat: add Reporter and Story database models"
```

---

### Task 4: Build Auth Endpoints + Seed Data

**Files:**
- Create: `/Users/admin/Desktop/newsflow-api/app/schemas/__init__.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/schemas/auth.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/deps.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/routers/__init__.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/routers/auth.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/main.py` (add seed data)

**Step 1: Create auth schemas**

`app/schemas/auth.py`:
```python
from pydantic import BaseModel


class OTPRequest(BaseModel):
    phone: str


class OTPVerify(BaseModel):
    phone: str
    otp: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ReporterResponse(BaseModel):
    id: str
    name: str
    phone: str
    area_name: str
    organization: str

    model_config = {"from_attributes": True}
```

`app/schemas/__init__.py`:
```python
from .auth import OTPRequest, OTPVerify, Token, ReporterResponse
```

**Step 2: Create deps.py (JWT helpers + current user dependency)**

`app/deps.py`:
```python
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models.reporter import Reporter

security = HTTPBearer()


def create_access_token(reporter_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": reporter_id, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_reporter(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Reporter:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        reporter_id: str = payload.get("sub")
        if reporter_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    reporter = db.query(Reporter).filter(Reporter.id == reporter_id).first()
    if reporter is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reporter not found")
    return reporter
```

**Step 3: Create auth router**

`app/routers/__init__.py`: empty file

`app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import create_access_token, get_current_reporter
from ..models.reporter import Reporter
from ..schemas.auth import OTPRequest, OTPVerify, ReporterResponse, Token

router = APIRouter()


@router.post("/request-otp")
def request_otp(body: OTPRequest, db: Session = Depends(get_db)):
    reporter = db.query(Reporter).filter(Reporter.phone == body.phone).first()
    if not reporter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    # In production: send real OTP via SMS gateway
    return {"message": "OTP sent", "phone": body.phone}


@router.post("/verify-otp", response_model=Token)
def verify_otp(body: OTPVerify, db: Session = Depends(get_db)):
    if body.otp != settings.HARDCODED_OTP:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")

    reporter = db.query(Reporter).filter(Reporter.phone == body.phone).first()
    if not reporter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")

    token = create_access_token(reporter.id)
    return Token(access_token=token)


@router.get("/me", response_model=ReporterResponse)
def get_me(reporter: Reporter = Depends(get_current_reporter)):
    return reporter
```

**Step 4: Add seed data to main.py**

Add this function to `/Users/admin/Desktop/newsflow-api/app/main.py` after `Base.metadata.create_all(...)`:

```python
def seed_data():
    from .database import SessionLocal
    from .models.reporter import Reporter
    db = SessionLocal()
    try:
        if db.query(Reporter).count() == 0:
            dummy = Reporter(
                name="Satrajit Mohapatra",
                phone="+919876543210",
                area_name="ନୟାଗଡ଼",
                organization="Dharitri News Network",
            )
            db.add(dummy)
            db.commit()
    finally:
        db.close()

seed_data()
```

**Step 5: Test auth flow**

```bash
cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && uvicorn app.main:app --reload --port 8000 &
sleep 2

# Request OTP
curl -s -X POST http://localhost:8000/auth/request-otp -H "Content-Type: application/json" -d '{"phone": "+919876543210"}'
# Expected: {"message":"OTP sent","phone":"+919876543210"}

# Verify OTP
TOKEN=$(curl -s -X POST http://localhost:8000/auth/verify-otp -H "Content-Type: application/json" -d '{"phone": "+919876543210", "otp": "123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo $TOKEN

# Get profile
curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
# Expected: {"id":"...","name":"Satrajit Mohapatra","phone":"+919876543210","area_name":"ନୟାଗଡ଼","organization":"Dharitri News Network"}

kill %1
```

**Step 6: Commit**

```bash
cd /Users/admin/Desktop/newsflow-api && git add . && git commit -m "feat: add auth endpoints with hardcoded OTP and seed data"
```

---

### Task 5: Build Story CRUD Endpoints

**Files:**
- Create: `/Users/admin/Desktop/newsflow-api/app/schemas/story.py`
- Create: `/Users/admin/Desktop/newsflow-api/app/routers/stories.py`

**Step 1: Create story schemas**

`app/schemas/story.py`:
```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ParagraphSchema(BaseModel):
    id: str
    text: str = ""
    photo_path: Optional[str] = None
    created_at: Optional[str] = None


class StoryCreate(BaseModel):
    headline: str = ""
    category: Optional[str] = None
    location: Optional[str] = None
    paragraphs: list[ParagraphSchema] = []


class StoryUpdate(BaseModel):
    headline: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    paragraphs: Optional[list[ParagraphSchema]] = None


class StoryResponse(BaseModel):
    id: str
    reporter_id: str
    headline: str
    category: Optional[str]
    location: Optional[str]
    paragraphs: list[dict]
    status: str
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

**Step 2: Create stories router**

`app/routers/stories.py`:
```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_reporter
from ..models.reporter import Reporter
from ..models.story import Story
from ..schemas.story import StoryCreate, StoryResponse, StoryUpdate

router = APIRouter()


@router.post("", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
def create_story(
    body: StoryCreate,
    reporter: Reporter = Depends(get_current_reporter),
    db: Session = Depends(get_db),
):
    story = Story(
        reporter_id=reporter.id,
        headline=body.headline,
        category=body.category,
        location=body.location,
        paragraphs=[p.model_dump() for p in body.paragraphs],
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


@router.get("", response_model=list[StoryResponse])
def list_stories(
    reporter: Reporter = Depends(get_current_reporter),
    db: Session = Depends(get_db),
):
    stories = (
        db.query(Story)
        .filter(Story.reporter_id == reporter.id)
        .order_by(
            # Drafts first, then by updated_at desc
            (Story.status != "draft"),
            Story.updated_at.desc(),
        )
        .limit(20)
        .all()
    )
    return stories


@router.get("/{story_id}", response_model=StoryResponse)
def get_story(
    story_id: str,
    reporter: Reporter = Depends(get_current_reporter),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == story_id, Story.reporter_id == reporter.id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    return story


@router.put("/{story_id}", response_model=StoryResponse)
def update_story(
    story_id: str,
    body: StoryUpdate,
    reporter: Reporter = Depends(get_current_reporter),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == story_id, Story.reporter_id == reporter.id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    if body.headline is not None:
        story.headline = body.headline
    if body.category is not None:
        story.category = body.category
    if body.location is not None:
        story.location = body.location
    if body.paragraphs is not None:
        story.paragraphs = [p.model_dump() for p in body.paragraphs]

    story.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(story)
    return story


@router.post("/{story_id}/submit", response_model=StoryResponse)
def submit_story(
    story_id: str,
    reporter: Reporter = Depends(get_current_reporter),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == story_id, Story.reporter_id == reporter.id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    if story.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only drafts can be submitted")

    story.status = "submitted"
    story.submitted_at = datetime.now(timezone.utc)
    story.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(story)
    return story
```

**Step 3: Update schemas/__init__.py**

```python
from .auth import OTPRequest, OTPVerify, Token, ReporterResponse
from .story import StoryCreate, StoryUpdate, StoryResponse
```

**Step 4: Test story CRUD**

```bash
cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && uvicorn app.main:app --reload --port 8000 &
sleep 2

# Get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/verify-otp -H "Content-Type: application/json" -d '{"phone": "+919876543210", "otp": "123456"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create story
curl -s -X POST http://localhost:8000/stories -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"headline": "Test", "paragraphs": [{"id": "1", "text": "Hello world"}]}'

# List stories
curl -s http://localhost:8000/stories -H "Authorization: Bearer $TOKEN"

kill %1
```

**Step 5: Commit**

```bash
cd /Users/admin/Desktop/newsflow-api && git add . && git commit -m "feat: add story CRUD endpoints with draft/submit flow"
```

---

### Task 6: Create Flutter API Client for Backend

**Files:**
- Create: `/Users/admin/Desktop/newsflow/lib/core/services/api_service.dart`
- Create: `/Users/admin/Desktop/newsflow/lib/core/services/api_config.dart`
- Modify: `/Users/admin/Desktop/newsflow/pubspec.yaml` (add shared_preferences)

**Step 1: Add shared_preferences to pubspec.yaml**

Add under `dependencies:` in `/Users/admin/Desktop/newsflow/pubspec.yaml`:
```yaml
  shared_preferences: ^2.3.0
```

Run:
```bash
cd /Users/admin/Desktop/newsflow && flutter pub get
```

**Step 2: Create API config**

`/Users/admin/Desktop/newsflow/lib/core/services/api_config.dart`:
```dart
class ApiConfig {
  ApiConfig._();

  // For web: localhost:8000. For mobile emulator: 10.0.2.2:8000
  static const String baseUrl = 'http://localhost:8000';
}
```

**Step 3: Create API service**

`/Users/admin/Desktop/newsflow/lib/core/services/api_service.dart`:
```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_config.dart';

// -- Response models --

class ReporterProfile {
  final String id;
  final String name;
  final String phone;
  final String areaName;
  final String organization;

  const ReporterProfile({
    required this.id,
    required this.name,
    required this.phone,
    required this.areaName,
    required this.organization,
  });

  factory ReporterProfile.fromJson(Map<String, dynamic> json) {
    return ReporterProfile(
      id: json['id'] as String,
      name: json['name'] as String,
      phone: json['phone'] as String,
      areaName: json['area_name'] as String? ?? '',
      organization: json['organization'] as String? ?? '',
    );
  }
}

class StoryDto {
  final String id;
  final String reporterId;
  final String headline;
  final String? category;
  final String? location;
  final List<Map<String, dynamic>> paragraphs;
  final String status;
  final DateTime? submittedAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  const StoryDto({
    required this.id,
    required this.reporterId,
    required this.headline,
    this.category,
    this.location,
    required this.paragraphs,
    required this.status,
    this.submittedAt,
    required this.createdAt,
    required this.updatedAt,
  });

  factory StoryDto.fromJson(Map<String, dynamic> json) {
    return StoryDto(
      id: json['id'] as String,
      reporterId: json['reporter_id'] as String,
      headline: json['headline'] as String? ?? '',
      category: json['category'] as String?,
      location: json['location'] as String?,
      paragraphs: (json['paragraphs'] as List<dynamic>?)
              ?.map((p) => Map<String, dynamic>.from(p as Map))
              .toList() ??
          [],
      status: json['status'] as String? ?? 'draft',
      submittedAt: json['submitted_at'] != null
          ? DateTime.parse(json['submitted_at'] as String)
          : null,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}

// -- API Service --

class ApiService {
  late final Dio _dio;
  String? _token;

  ApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
      ),
    );
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_token != null) {
          options.headers['Authorization'] = 'Bearer $_token';
        }
        handler.next(options);
      },
    ));
  }

  void setToken(String? token) => _token = token;

  // -- Auth --

  Future<void> requestOtp(String phone) async {
    await _dio.post('/auth/request-otp', data: {'phone': phone});
  }

  Future<({String token, ReporterProfile reporter})> verifyOtp(String phone, String otp) async {
    final res = await _dio.post('/auth/verify-otp', data: {'phone': phone, 'otp': otp});
    final token = res.data['access_token'] as String;
    _token = token;

    final meRes = await _dio.get('/auth/me');
    final reporter = ReporterProfile.fromJson(meRes.data as Map<String, dynamic>);
    return (token: token, reporter: reporter);
  }

  Future<ReporterProfile> getMe() async {
    final res = await _dio.get('/auth/me');
    return ReporterProfile.fromJson(res.data as Map<String, dynamic>);
  }

  // -- Stories --

  Future<StoryDto> createStory({
    String headline = '',
    String? category,
    String? location,
    List<Map<String, dynamic>> paragraphs = const [],
  }) async {
    final res = await _dio.post('/stories', data: {
      'headline': headline,
      'category': category,
      'location': location,
      'paragraphs': paragraphs,
    });
    return StoryDto.fromJson(res.data as Map<String, dynamic>);
  }

  Future<StoryDto> updateStory(String storyId, {
    String? headline,
    String? category,
    String? location,
    List<Map<String, dynamic>>? paragraphs,
  }) async {
    final data = <String, dynamic>{};
    if (headline != null) data['headline'] = headline;
    if (category != null) data['category'] = category;
    if (location != null) data['location'] = location;
    if (paragraphs != null) data['paragraphs'] = paragraphs;

    final res = await _dio.put('/stories/$storyId', data: data);
    return StoryDto.fromJson(res.data as Map<String, dynamic>);
  }

  Future<List<StoryDto>> listStories() async {
    final res = await _dio.get('/stories');
    return (res.data as List<dynamic>)
        .map((e) => StoryDto.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<StoryDto> submitStory(String storyId) async {
    final res = await _dio.post('/stories/$storyId/submit');
    return StoryDto.fromJson(res.data as Map<String, dynamic>);
  }
}

// -- Provider --

final apiServiceProvider = Provider<ApiService>((ref) => ApiService());
```

**Step 4: Verify build**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web 2>&1 | tail -5
```

**Step 5: Commit**

```bash
cd /Users/admin/Desktop/newsflow && git add pubspec.yaml pubspec.lock lib/core/services/api_service.dart lib/core/services/api_config.dart && git commit -m "feat: add API client service for backend communication"
```

---

### Task 7: Build Auth State + Login Screen

**Files:**
- Create: `/Users/admin/Desktop/newsflow/lib/features/auth/providers/auth_provider.dart`
- Create: `/Users/admin/Desktop/newsflow/lib/features/auth/screens/login_screen.dart`

**Step 1: Create AuthNotifier**

`/Users/admin/Desktop/newsflow/lib/features/auth/providers/auth_provider.dart`:
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/services/api_service.dart';

class AuthState {
  final ReporterProfile? reporter;
  final String? token;
  final bool isLoading;
  final String? error;
  final bool otpSent;

  const AuthState({
    this.reporter,
    this.token,
    this.isLoading = false,
    this.error,
    this.otpSent = false,
  });

  bool get isLoggedIn => token != null && reporter != null;

  AuthState copyWith({
    ReporterProfile? reporter,
    String? token,
    bool? isLoading,
    String? error,
    bool clearError = false,
    bool? otpSent,
    bool clearToken = false,
    bool clearReporter = false,
  }) {
    return AuthState(
      reporter: clearReporter ? null : (reporter ?? this.reporter),
      token: clearToken ? null : (token ?? this.token),
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      otpSent: otpSent ?? this.otpSent,
    );
  }
}

class AuthNotifier extends Notifier<AuthState> {
  static const _tokenKey = 'jwt_token';

  @override
  AuthState build() => const AuthState();

  ApiService get _api => ref.read(apiServiceProvider);

  /// Try to auto-login using stored JWT.
  Future<bool> tryAutoLogin() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final prefs = await SharedPreferences.getInstance();
      final storedToken = prefs.getString(_tokenKey);
      if (storedToken == null) {
        state = state.copyWith(isLoading: false);
        return false;
      }

      _api.setToken(storedToken);
      final reporter = await _api.getMe();
      state = AuthState(reporter: reporter, token: storedToken);
      return true;
    } catch (_) {
      // Token expired or invalid — clear it
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_tokenKey);
      _api.setToken(null);
      state = const AuthState();
      return false;
    }
  }

  Future<void> requestOtp(String phone) async {
    state = state.copyWith(isLoading: true, clearError: true, otpSent: false);
    try {
      await _api.requestOtp(phone);
      state = state.copyWith(isLoading: false, otpSent: true);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: _extractError(e));
    }
  }

  Future<bool> verifyOtp(String phone, String otp) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final result = await _api.verifyOtp(phone, otp);

      // Store token
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_tokenKey, result.token);

      state = AuthState(reporter: result.reporter, token: result.token);
      return true;
    } catch (e) {
      state = state.copyWith(isLoading: false, error: _extractError(e));
      return false;
    }
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    _api.setToken(null);
    state = const AuthState();
  }

  String _extractError(dynamic e) {
    if (e is DioException && e.response?.data != null) {
      final data = e.response!.data;
      if (data is Map && data['detail'] != null) return data['detail'].toString();
    }
    return 'Something went wrong. Please try again.';
  }
}

// Need this import for DioException
import 'package:dio/dio.dart';

final authProvider = NotifierProvider<AuthNotifier, AuthState>(AuthNotifier.new);
```

**Step 2: Create LoginScreen**

`/Users/admin/Desktop/newsflow/lib/features/auth/screens/login_screen.dart`:

Build a clean login screen with:
- App logo/name at top ("NewsFlow" with gradient)
- Phone number TextField with +91 prefix
- "Get OTP" button → on success, show OTP TextField
- OTP TextField (6 digits)
- "Verify" button → on success, navigate to /home
- Error display
- Loading indicator during API calls

Use the existing design system: `AppColors`, `AppTypography`, `AppGradients`, `AppSpacing`, `LucideIcons`.

The screen should be a `ConsumerStatefulWidget` with TextEditingControllers for phone and OTP fields.

Key wiring:
```dart
final auth = ref.watch(authProvider);
final notifier = ref.read(authProvider.notifier);

// Request OTP
onTap: () => notifier.requestOtp('+91${_phoneController.text}')

// Verify OTP
onTap: () async {
  final success = await notifier.verifyOtp('+91${_phoneController.text}', _otpController.text);
  if (success && mounted) context.go('/home');
}
```

**Step 3: Verify build**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web 2>&1 | tail -5
```

**Step 4: Commit**

```bash
cd /Users/admin/Desktop/newsflow && git add lib/features/auth/ && git commit -m "feat: add auth provider and login screen with OTP flow"
```

---

### Task 8: Build Stories Provider + Rework Home Screen

**Files:**
- Create: `/Users/admin/Desktop/newsflow/lib/features/home/providers/stories_provider.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/features/home/screens/home_screen.dart`

**Step 1: Create StoriesNotifier**

`/Users/admin/Desktop/newsflow/lib/features/home/providers/stories_provider.dart`:
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/api_service.dart';

class StoriesState {
  final List<StoryDto> stories;
  final bool isLoading;
  final String? error;

  const StoriesState({
    this.stories = const [],
    this.isLoading = false,
    this.error,
  });

  List<StoryDto> get drafts => stories.where((s) => s.status == 'draft').toList();
  List<StoryDto> get submitted => stories.where((s) => s.status != 'draft').toList();

  StoriesState copyWith({
    List<StoryDto>? stories,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return StoriesState(
      stories: stories ?? this.stories,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class StoriesNotifier extends Notifier<StoriesState> {
  @override
  StoriesState build() => const StoriesState();

  ApiService get _api => ref.read(apiServiceProvider);

  Future<void> fetchStories() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final stories = await _api.listStories();
      state = StoriesState(stories: stories);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: 'Failed to load stories');
    }
  }

  Future<StoryDto?> createStory() async {
    try {
      return await _api.createStory();
    } catch (_) {
      return null;
    }
  }

  Future<void> submitStory(String storyId) async {
    try {
      await _api.submitStory(storyId);
      await fetchStories(); // Refresh list
    } catch (_) {}
  }
}

final storiesProvider = NotifierProvider<StoriesNotifier, StoriesState>(StoriesNotifier.new);
```

**Step 2: Rework HomeScreen to show real stories**

Modify `/Users/admin/Desktop/newsflow/lib/features/home/screens/home_screen.dart`:

- Import `authProvider` and `storiesProvider`
- In build: `ref.watch(authProvider)` for reporter name/area, `ref.watch(storiesProvider)` for stories
- Call `ref.read(storiesProvider.notifier).fetchStories()` on first build (use `ref.listen` or init pattern)
- Header: show `reporter.name` and `reporter.areaName` instead of static text
- Show `storiesState.drafts` as draft cards, `storiesState.submitted` as submitted cards
- Each card: headline (or "Untitled Draft"), status badge, paragraph count, time ago
- Tap card → `context.push('/create?storyId=${story.id}')`
- Show loading spinner while fetching
- Keep empty state when no stories exist
- Add a logout button in the header (bell icon → menu with logout option)

**Step 3: Verify build**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web 2>&1 | tail -5
```

**Step 4: Commit**

```bash
cd /Users/admin/Desktop/newsflow && git add lib/features/home/ && git commit -m "feat: wire home screen to backend with real story data"
```

---

### Task 9: Wire Notepad to Backend (Create/Update/Submit)

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/features/create_news/providers/create_news_provider.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/features/create_news/screens/notepad_screen.dart`

**Step 1: Add server sync to NotepadNotifier**

In `/Users/admin/Desktop/newsflow/lib/features/create_news/providers/create_news_provider.dart`:

- Add `String? _serverStoryId;` field
- Add `ApiService get _api => ref.read(apiServiceProvider);`
- Add `initWithNewStory()` method: calls `_api.createStory()` to get a server ID, stores it in `_serverStoryId`
- Add `initWithExistingStory(String storyId)` method: calls `_api.getStory(storyId)`, populates state from server data
- Add `_autoSave()` method: debounced call to `_api.updateStory(_serverStoryId, ...)` — called after every state change (paragraph add/edit/delete, headline change)
- Add `submitStory()` method: shows confirmation first, then calls `_api.submitStory(_serverStoryId)` and navigates back
- Use a `Timer? _autoSaveTimer` for debouncing (500ms delay)

Key pattern for auto-save:
```dart
void _scheduleAutoSave() {
  _autoSaveTimer?.cancel();
  _autoSaveTimer = Timer(const Duration(milliseconds: 800), () {
    _syncToServer();
  });
}

Future<void> _syncToServer() async {
  if (_serverStoryId == null) return;
  try {
    await _api.updateStory(
      _serverStoryId!,
      headline: state.headline,
      category: state.category,
      location: state.location,
      paragraphs: state.paragraphs.map((p) => {
        'id': p.id,
        'text': p.text,
        'photo_path': p.photoPath,
        'created_at': p.createdAt.toIso8601String(),
      }).toList(),
    );
  } catch (_) {
    // Silent fail — auto-save is best-effort
  }
}
```

Call `_scheduleAutoSave()` at the end of: `toggleRecording()` (after creating paragraph), `deleteParagraph()`, `updateParagraphText()`, `insertPhoto()`, `removePhoto()`, `setHeadline()`.

**Step 2: Update NotepadScreen to accept storyId param**

In `/Users/admin/Desktop/newsflow/lib/features/create_news/screens/notepad_screen.dart`:

- Accept optional `storyId` parameter
- In `initState`: if storyId provided, call `notifier.initWithExistingStory(storyId)`. Otherwise, call `notifier.initWithNewStory()`.
- Add confirmation dialog before submit:
```dart
Future<void> _confirmSubmit() async {
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text('ଦାଖଲ କରନ୍ତୁ?'),
      content: Text('ଏହି ଖବର ଦାଖଲ କରିବାକୁ ଚାହୁଁଛନ୍ତି?'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text('ନାହିଁ')),
        TextButton(onPressed: () => Navigator.pop(ctx, true), child: Text('ହଁ')),
      ],
    ),
  );
  if (confirmed == true) {
    await notifier.submitStory();
    if (mounted) context.go('/home');
  }
}
```

**Step 3: Update router to pass storyId**

In `/Users/admin/Desktop/newsflow/lib/core/router/app_router.dart`, update the `/create` route:
```dart
GoRoute(
  path: '/create',
  parentNavigatorKey: _rootNavigatorKey,
  builder: (_, state) {
    final storyId = state.uri.queryParameters['storyId'];
    return NotepadScreen(storyId: storyId);
  },
),
```

**Step 4: Verify build**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web 2>&1 | tail -5
```

**Step 5: Commit**

```bash
cd /Users/admin/Desktop/newsflow && git add lib/features/create_news/ lib/core/router/app_router.dart && git commit -m "feat: wire notepad to backend with auto-save and submit"
```

---

### Task 10: Add Auth Guard to Router + App Startup

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/core/router/app_router.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/app.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/main.dart`

**Step 1: Update router with auth redirect**

In `/Users/admin/Desktop/newsflow/lib/core/router/app_router.dart`:

- Import `authProvider`
- Make `appRouter` depend on a `ProviderRef` or use `GoRouter.redirect`
- Add redirect logic: if not logged in and not on `/login`, redirect to `/login`
- Add `/login` route pointing to `LoginScreen`

Since GoRouter needs to be reactive to auth state, convert `appRouter` to use `riverpod`:

```dart
final appRouterProvider = Provider<GoRouter>((ref) {
  final auth = ref.watch(authProvider);

  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/home',
    redirect: (context, state) {
      final isLoggedIn = auth.isLoggedIn;
      final isOnLogin = state.matchedLocation == '/login';

      if (!isLoggedIn && !isOnLogin) return '/login';
      if (isLoggedIn && isOnLogin) return '/home';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
      ShellRoute(
        navigatorKey: _shellNavigatorKey,
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
          GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
        ],
      ),
      GoRoute(
        path: '/create',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (_, state) {
          final storyId = state.uri.queryParameters['storyId'];
          return NotepadScreen(storyId: storyId);
        },
      ),
    ],
  );
});
```

**Step 2: Update app.dart to use provider-based router**

```dart
class NewsFlowApp extends ConsumerWidget {
  const NewsFlowApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    return MaterialApp.router(
      title: 'NewsFlow',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      routerConfig: router,
    );
  }
}
```

**Step 3: Add auto-login attempt on startup**

In `main.dart`, after `WidgetsFlutterBinding.ensureInitialized()`:
- The auto-login happens in AuthNotifier.tryAutoLogin() which LoginScreen or a splash screen should call.
- Simplest approach: LoginScreen calls `tryAutoLogin()` on init, and if it succeeds, the redirect automatically sends user to `/home`.

**Step 4: Verify build**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web 2>&1 | tail -5
```

**Step 5: Commit**

```bash
cd /Users/admin/Desktop/newsflow && git add lib/ && git commit -m "feat: add auth guard and auto-login on app startup"
```

---

### Task 11: End-to-End Test

**Step 1: Start backend**

```bash
cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && rm -f newsflow.db && uvicorn app.main:app --reload --port 8000
```

(Delete DB to start fresh with seed data)

**Step 2: Start Flutter web**

```bash
cd /Users/admin/Desktop/newsflow && flutter run -d chrome --web-port 8080
```

**Step 3: Verify flow in Chrome**

1. App opens → redirected to login screen
2. Enter phone: 9876543210 → tap "Get OTP"
3. Enter OTP: 123456 → tap "Verify"
4. Redirected to home → see "Satrajit Mohapatra" and "ନୟାଗଡ଼"
5. Home shows empty state (no stories yet)
6. Tap "+" → notepad opens with empty state
7. Record voice → text appears without duplication
8. Stop recording → paragraph saved, auto-saves to server
9. Tap back → home shows the draft
10. Tap draft → notepad reopens with saved content
11. Tap submit → confirmation dialog → submitted
12. Home shows story under "Submitted" section

**Step 4: Final commit**

```bash
cd /Users/admin/Desktop/newsflow && git add -A && git commit -m "feat: backend integration complete — auth, stories, auto-save"
```
