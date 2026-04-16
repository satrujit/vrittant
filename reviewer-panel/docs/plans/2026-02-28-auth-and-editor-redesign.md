# Auth System & Voice Editor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add OTP-based authentication with user types/entitlements, then redesign the ReviewPage with inline voice transcription and AI-powered text editing via Sarvam LLM.

**Architecture:** Phase 1 builds a unified User model (replacing Reporter) with an Entitlement table for page-level access control, OTP login flow, and JWT-protected endpoints. Phase 2 redesigns the ReviewPage with a custom TipTap TranscriptionMark for inline orange live transcription, and an AI sparkle mode that sends selected text + spoken instructions to the Sarvam `sarvam-m` LLM for intelligent editing.

**Tech Stack:** FastAPI 0.115 + SQLAlchemy 2.0 (backend), React 19 + Vite + TipTap (frontend), Web Speech API (STT), Sarvam AI `sarvam-m` (LLM)

---

## Phase 1: Authentication & Authorization

### Task 1: Rename Reporter Model to User Model

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/models/reporter.py` → rename to `user.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/models/__init__.py`

**Step 1: Create the new User model file**

Create `/Users/admin/Desktop/newsflow-api/app/models/user.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=True)
    user_type = Column(String, nullable=False, default="reporter")  # reporter | reviewer | admin
    area_name = Column(String, nullable=False, default="")
    organization = Column(String, nullable=False, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    stories = relationship("Story", back_populates="reporter")
    entitlements = relationship("Entitlement", back_populates="user", cascade="all, delete-orphan")


class Entitlement(Base):
    __tablename__ = "entitlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    page_key = Column(String, nullable=False)  # dashboard | stories | review | editions | reporters | social_export

    user = relationship("User", back_populates="entitlements")
```

**Step 2: Update `__init__.py`**

Edit `/Users/admin/Desktop/newsflow-api/app/models/__init__.py`:

```python
from .edition import Edition, EditionPage, EditionPageStory
from .user import User, Entitlement
from .story import Story

__all__ = ["Edition", "EditionPage", "EditionPageStory", "User", "Entitlement", "Story"]
```

**Step 3: Update Story model FK reference**

Edit `/Users/admin/Desktop/newsflow-api/app/models/story.py` — change the `reporter_id` ForeignKey from `"reporters.id"` to `"users.id"` and update the relationship back_populates. The column name stays `reporter_id` for backward compatibility.

**Step 4: Delete old reporter.py**

Remove `/Users/admin/Desktop/newsflow-api/app/models/reporter.py`.

**Step 5: Verify the server starts**

Run: `cd /Users/admin/Desktop/newsflow-api && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
Expected: Server starts without import errors (DB will be recreated).

---

### Task 2: Update Auth Schemas and Dependencies

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/schemas/auth.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/schemas/__init__.py`
- Modify: `/Users/admin/Desktop/newsflow-api/app/deps.py`

**Step 1: Update auth schemas**

Edit `/Users/admin/Desktop/newsflow-api/app/schemas/auth.py`:

```python
from typing import Optional
from pydantic import BaseModel


class OTPRequest(BaseModel):
    phone: str


class OTPVerify(BaseModel):
    phone: str
    otp: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EntitlementResponse(BaseModel):
    page_key: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str] = None
    user_type: str
    area_name: str
    organization: str
    entitlements: list[EntitlementResponse] = []

    model_config = {"from_attributes": True}
```

**Step 2: Update schemas `__init__.py`**

```python
from .auth import OTPRequest, OTPVerify, Token, UserResponse, EntitlementResponse
from .story import StoryCreate, StoryUpdate, StoryResponse
```

**Step 3: Update deps.py**

Edit `/Users/admin/Desktop/newsflow-api/app/deps.py`:

```python
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models.user import User

security = HTTPBearer()


def create_access_token(user_id: str, user_type: str = "reporter") -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "user_type": user_type, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# Backward-compat alias — existing code that uses get_current_reporter still works
get_current_reporter = get_current_user
```

---

### Task 3: Update Auth Router

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/routers/auth.py`

**Step 1: Rewrite auth.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import create_access_token, get_current_user
from ..models.user import User
from ..schemas.auth import OTPRequest, OTPVerify, Token, UserResponse

router = APIRouter()


@router.post("/request-otp")
def request_otp(body: OTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")
    return {"message": "OTP sent", "phone": body.phone}


@router.post("/verify-otp", response_model=Token)
def verify_otp(body: OTPVerify, db: Session = Depends(get_db)):
    if body.otp != settings.HARDCODED_OTP:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")

    user = db.query(User).filter(User.phone == body.phone).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not registered")

    token = create_access_token(user.id, user.user_type)
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return user
```

---

### Task 4: Update Admin Router References

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/routers/admin.py`

**Step 1: Update imports**

Change:
```python
from ..models.reporter import Reporter
```
To:
```python
from ..models.user import User
```

**Step 2: Replace all `Reporter` references with `User`**

In all queries, replace `db.query(Reporter)` → `db.query(User)` and `Reporter.id` → `User.id`, etc. In `AdminReporterInfo`, `AdminReporterResponse`, and `AdminReporterListResponse` schemas — keep names as-is for API compat but query from `User`. Also add `from ..models.user import User` at top.

**Step 3: Update `admin_list_reporters`**

Add a filter for reporter user_type: `db.query(User).filter(User.user_type == "reporter")` so the reporters page only shows reporters, not reviewers/admins.

---

### Task 5: Update Sarvam Router

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/routers/sarvam.py`

**Step 1: Update imports**

Change:
```python
from ..deps import get_current_reporter
from ..models.reporter import Reporter
```
To:
```python
from ..deps import get_current_user
from ..models.user import User
```

**Step 2: Update LLM endpoint dependency**

Change `reporter: Reporter = Depends(get_current_reporter)` to `user: User = Depends(get_current_user)`.

**Step 3: Update WebSocket auth**

In `_authenticate_ws`, the JWT decode stays the same — it returns user_id from `sub` claim. No change needed since it only validates the token.

---

### Task 6: Update Stories Router

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/routers/stories.py`

**Step 1: Update import**

Change `from ..models.reporter import Reporter` to `from ..models.user import User` and update any references.

---

### Task 7: Update main.py Seed Data

**Files:**
- Modify: `/Users/admin/Desktop/newsflow-api/app/main.py`

**Step 1: Update imports and seed data**

```python
from .models.user import User, Entitlement
```

Update `seed_data()` to:
1. Create the existing reporter: Satrajit Mohapatra with `user_type="reporter"`
2. Create a reviewer account: name="Editor Reviewer", phone="+919999999999", user_type="reviewer"
3. Add entitlements for the reviewer: all 6 page_keys (dashboard, stories, review, editions, reporters, social_export)

```python
def seed_data():
    from .database import SessionLocal
    from .models.user import User, Entitlement
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            # Reporter
            reporter = User(
                name="Satrajit Mohapatra",
                phone="+919876543210",
                area_name="ନୟାଗଡ଼",
                organization="Dharitri News Network",
                user_type="reporter",
            )
            db.add(reporter)

            # Reviewer
            reviewer = User(
                name="Editor Reviewer",
                phone="+919999999999",
                user_type="reviewer",
                organization="Pragativadi",
            )
            db.add(reviewer)
            db.flush()

            # Reviewer entitlements
            for page_key in ["dashboard", "stories", "review", "editions", "reporters", "social_export"]:
                db.add(Entitlement(user_id=reviewer.id, page_key=page_key))

            db.commit()
    finally:
        db.close()
```

**Step 2: Delete the old SQLite database and restart**

Run: `rm /Users/admin/Desktop/newsflow-api/newsflow.db && cd /Users/admin/Desktop/newsflow-api && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

Expected: Server starts, seed data creates both users, tables are `users` and `entitlements`.

**Step 3: Verify auth endpoints work**

Run: `curl -X POST http://localhost:8000/auth/request-otp -H "Content-Type: application/json" -d '{"phone": "+919999999999"}'`
Expected: `{"message":"OTP sent","phone":"+919999999999"}`

Run: `curl -X POST http://localhost:8000/auth/verify-otp -H "Content-Type: application/json" -d '{"phone": "+919999999999", "otp": "123456"}'`
Expected: `{"access_token":"eyJ...","token_type":"bearer"}`

Run: `curl http://localhost:8000/auth/me -H "Authorization: Bearer <token_from_above>"`
Expected: JSON with user info including entitlements array.

---

### Task 8: Frontend — API Service Auth Layer

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/services/api.js`

**Step 1: Add token management and auth header**

Add these functions at the top of api.js after `API_BASE`:

```javascript
// Token management
export function getAuthToken() {
  return localStorage.getItem('vr_token');
}

export function setAuthToken(token) {
  localStorage.setItem('vr_token', token);
}

export function clearAuthToken() {
  localStorage.removeItem('vr_token');
}
```

**Step 2: Update `apiFetch` to include auth header**

Add the token to headers in `apiFetch`:

```javascript
async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const token = getAuthToken();
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
      ...options,
    });

    if (response.status === 401) {
      clearAuthToken();
      window.location.href = '/login';
      throw new Error('Session expired');
    }
    // ... rest stays the same
```

**Step 3: Add auth API functions**

```javascript
// Auth endpoints (no token needed)
export async function requestOTP(phone) {
  return apiFetch('/auth/request-otp', {
    method: 'POST',
    body: JSON.stringify({ phone }),
  });
}

export async function verifyOTP(phone, otp) {
  return apiFetch('/auth/verify-otp', {
    method: 'POST',
    body: JSON.stringify({ phone, otp }),
  });
}

export async function fetchCurrentUser() {
  return apiFetch('/auth/me');
}
```

**Step 4: Add LLM chat function**

```javascript
export async function llmChat(messages, options = {}) {
  return apiFetch('/api/llm/chat', {
    method: 'POST',
    body: JSON.stringify({
      messages,
      model: options.model || 'sarvam-m',
      temperature: options.temperature,
      max_tokens: options.max_tokens,
    }),
  });
}
```

---

### Task 9: Frontend — AuthContext Provider

**Files:**
- Create: `/Users/admin/Desktop/newsflow/reviewer-panel/src/contexts/AuthContext.jsx`

**Step 1: Create AuthContext**

```jsx
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { fetchCurrentUser, setAuthToken, clearAuthToken, getAuthToken } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check for existing token on mount
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      fetchCurrentUser()
        .then(setUser)
        .catch(() => {
          clearAuthToken();
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback((token) => {
    setAuthToken(token);
    return fetchCurrentUser().then((u) => {
      setUser(u);
      return u;
    });
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    setUser(null);
  }, []);

  const hasEntitlement = useCallback(
    (pageKey) => {
      if (!user?.entitlements) return false;
      return user.entitlements.some((e) => e.page_key === pageKey);
    },
    [user]
  );

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, hasEntitlement }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
```

---

### Task 10: Frontend — LoginPage

**Files:**
- Create: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/LoginPage.jsx`
- Create: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/LoginPage.module.css`

**Step 1: Create LoginPage component**

A two-step form: Step 1 = phone input, Step 2 = OTP input. Uses Vrittant branding (coral color, logo). Calls `requestOTP` then `verifyOTP`, then `login(token)` from AuthContext, then navigates to `/`.

Key states: `step` (phone | otp), `phone`, `otp`, `error`, `loading`.

**Step 2: Create LoginPage.module.css**

Centered card layout with coral accent. Input fields, submit button styled with design tokens. Newspaper logo at top.

**Step 3: Add i18n keys**

Add to both `en.json` and `or.json`:
```json
"auth": {
  "loginTitle": "Sign In",
  "phoneLabel": "Phone Number",
  "phonePlaceholder": "+91...",
  "sendOTP": "Send OTP",
  "otpLabel": "Enter OTP",
  "otpPlaceholder": "123456",
  "verifyOTP": "Verify",
  "invalidPhone": "Phone number not registered",
  "invalidOTP": "Invalid OTP",
  "logout": "Logout"
}
```

---

### Task 11: Frontend — Protected Routes & App Integration

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/App.jsx`
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/components/layout/Sidebar.jsx`

**Step 1: Update App.jsx**

Wrap the entire app in `<AuthProvider>`. Add `<Route path="/login" element={<LoginPage />} />`. Wrap layout routes in a `<ProtectedRoute>` component that checks for auth and redirects to `/login`.

```jsx
import { AuthProvider } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <I18nProvider defaultLocale="or">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/stories" element={<AllStoriesPage />} />
                <Route path="/reporters" element={<ReportersPage />} />
                <Route path="/reporters/:id" element={<ReporterDetailPage />} />
                <Route path="/buckets" element={<EditionsPage />} />
                <Route path="/buckets/:editionId" element={<BucketsPage />} />
              </Route>
              <Route path="/review/:id" element={<ReviewPage />} />
              <Route path="/review/:id/social" element={<SocialExportPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </I18nProvider>
  );
}
```

**Step 2: Create ProtectedRoute component**

Create `/Users/admin/Desktop/newsflow/reviewer-panel/src/components/ProtectedRoute.jsx`:

```jsx
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) return null; // or a spinner
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export default ProtectedRoute;
```

**Step 3: Update Sidebar to use auth**

- Import `useAuth` and use `hasEntitlement` to conditionally render nav items
- Replace hardcoded "Alex Rivera" with `user.name` from auth context
- Add logout button

**Step 4: Verify the login flow**

1. Open `http://localhost:5174` → should redirect to `/login`
2. Enter phone `+919999999999` → click Send OTP
3. Enter OTP `123456` → click Verify
4. Should redirect to dashboard with full navigation

**Step 5: Commit Phase 1**

```bash
git add -A && git commit -m "feat: add OTP authentication with user types and entitlements"
```

---

## Phase 2: ReviewPage Redesign

### Task 12: Install TipTap Table Extensions

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/package.json`

**Step 1: Install dependencies**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npm install @tiptap/extension-table @tiptap/extension-table-row @tiptap/extension-table-cell @tiptap/extension-table-header`

---

### Task 13: Create Custom TranscriptionMark Extension

**Files:**
- Create: `/Users/admin/Desktop/newsflow/reviewer-panel/src/extensions/TranscriptionMark.js`

**Step 1: Create the TipTap mark extension**

```javascript
import { Mark } from '@tiptap/core';

const TranscriptionMark = Mark.create({
  name: 'transcription',

  addAttributes() {
    return {};
  },

  parseHTML() {
    return [{ tag: 'span[data-transcription]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', { ...HTMLAttributes, 'data-transcription': '', style: 'color: #FA6C38; font-weight: 500;' }, 0];
  },
});

export default TranscriptionMark;
```

This mark renders inline text in coral orange (#FA6C38) to show live transcription.

---

### Task 14: Redesign ReviewPage — Editor Layout & Voice Dictation

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/ReviewPage.jsx`
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/pages/ReviewPage.module.css`

This is the largest task. The full ReviewPage gets rewritten with these features:

**Step 1: Update imports**

Add new imports:
```javascript
import { Sparkles, Table as TableIcon } from 'lucide-react';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import TranscriptionMark from '../extensions/TranscriptionMark';
import { useAuth } from '../contexts/AuthContext';
import { llmChat } from '../services/api';
```

**Step 2: Add table extensions to TipTap editor config**

Add `Table.configure({ resizable: true })`, `TableRow`, `TableCell`, `TableHeader`, and `TranscriptionMark` to the extensions array.

**Step 3: Implement enhanced voice dictation**

New state variables:
```javascript
const [voiceMode, setVoiceMode] = useState('idle'); // idle | dictating | sparkle-listening | sparkle-processing
const [hasSelection, setHasSelection] = useState(false);
const [interimText, setInterimText] = useState('');
```

Voice dictation logic:
- When `voiceMode === 'dictating'`:
  - Add class `styles.editorMuted` to editor wrapper (opacity 0.4 on existing text)
  - Interim results: remove previous transcription mark, insert new one at cursor with `transcription` mark
  - Final results: remove mark, insert as plain text
- Track editor selection state via `editor.on('selectionUpdate')` to toggle `hasSelection`

**Step 4: Implement AI sparkle mode**

When `hasSelection` is true and user clicks sparkle button:
1. Set `voiceMode` to `'sparkle-listening'`
2. Start speech recognition
3. On final result: set `voiceMode` to `'sparkle-processing'`, get the spoken command
4. Get selected text from editor: `editor.state.doc.textBetween(from, to)`
5. Call `llmChat()` with system prompt + instruction + selected text
6. Replace selection with LLM response: `editor.chain().focus().deleteSelection().insertContent(response).run()`
7. Set `voiceMode` back to `'idle'`

**Step 5: Add table controls to toolbar**

Add a "Insert Table" button that calls `editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()`.

**Step 6: Modernize UI layout**

- Top bar: Back button + category/status chips + Save Draft
- Clean editor area with headline input
- Toolbar below headline (existing formatting + table + voice/sparkle)
- Bottom action bar (mobile-inspired): settings gear, attachment icon, sparkle/mic toggle, send/save button
- Voice indicator bar: "ସିଧା ଲିପିବଦ୍ଧ" with animated red dot when recording
- Sparkle processing indicator: "AI ସମ୍ପାଦନା ଚାଲୁଅଛି..." with spinner

**Step 7: Update CSS module**

Key new styles:
- `.editorMuted .tiptapEditor` — `opacity: 0.4` on existing content during dictation
- `.transcriptionIndicator` — orange pulsing bar showing "Direct Transcription" text
- `.sparkleBtn` — sparkle button styles (appears when text selected)
- `.sparkleProcessing` — loading state with spinner
- `.bottomBar` — fixed bottom action bar
- `.chipRow` — category + status chips at top
- Table styles for TipTap tables

---

### Task 15: Add i18n Keys for Editor

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/i18n/locales/en.json`
- Modify: `/Users/admin/Desktop/newsflow/reviewer-panel/src/i18n/locales/or.json`

**Step 1: Add new keys**

English:
```json
"review": {
  ...existing keys...,
  "directTranscription": "Direct Transcription",
  "sparkleCommand": "Speak your editing instruction...",
  "sparkleProcessing": "AI editing in progress...",
  "insertTable": "Insert Table",
  "addRow": "Add Row",
  "addColumn": "Add Column",
  "deleteRow": "Delete Row",
  "deleteColumn": "Delete Column",
  "deleteTable": "Delete Table",
  "advancedSettings": "Advanced Settings"
}
```

Odia:
```json
"review": {
  ...existing keys...,
  "directTranscription": "ସିଧା ଲିପିବଦ୍ଧ",
  "sparkleCommand": "ଆପଣଙ୍କ ସମ୍ପାଦନା ନିର୍ଦ୍ଦେଶ କୁହନ୍ତୁ...",
  "sparkleProcessing": "AI ସମ୍ପାଦନା ଚାଲୁଅଛି...",
  "insertTable": "ଟେବୁଲ ଯୋଡ଼ନ୍ତୁ",
  "addRow": "ଧାଡ଼ି ଯୋଡ଼ନ୍ତୁ",
  "addColumn": "ସ୍ତମ୍ଭ ଯୋଡ଼ନ୍ତୁ",
  "deleteRow": "ଧାଡ଼ି ବାହାର କରନ୍ତୁ",
  "deleteColumn": "ସ୍ତମ୍ଭ ବାହାର କରନ୍ତୁ",
  "deleteTable": "ଟେବୁଲ ବାହାର କରନ୍ତୁ",
  "advancedSettings": "ଉନ୍ନତ ସେଟିଂସ"
}
```

---

### Task 16: Verify & Test Complete Flow

**Step 1: Start both servers**

Backend: `cd /Users/admin/Desktop/newsflow-api && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
Frontend: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npm run dev`

**Step 2: Test login flow**

1. Open app → redirected to `/login`
2. Enter `+919999999999` → Send OTP
3. Enter `123456` → Verify
4. Dashboard loads with navigation

**Step 3: Test voice dictation**

1. Navigate to a story review page
2. Click mic button → should enter dictation mode
3. Speak in Odia → orange text appears inline
4. Stop recording → text turns normal

**Step 4: Test AI sparkle editing**

1. Select some text in the editor
2. Mic button should change to sparkle
3. Click sparkle → speak a command
4. Selected text should be replaced with LLM response

**Step 5: Test table insertion**

1. Click table button in toolbar
2. A 3x3 table should appear
3. Can type in cells, add/delete rows/columns

**Step 6: Commit Phase 2**

```bash
git add -A && git commit -m "feat: redesign ReviewPage with voice dictation and AI sparkle editing"
```

---

## Summary of All Files

### Backend (create/modify):
1. Create: `app/models/user.py` (User + Entitlement models)
2. Delete: `app/models/reporter.py`
3. Modify: `app/models/__init__.py`
4. Modify: `app/models/story.py` (FK reference)
5. Modify: `app/schemas/auth.py` (UserResponse + EntitlementResponse)
6. Modify: `app/schemas/__init__.py`
7. Modify: `app/deps.py` (get_current_user, updated token)
8. Modify: `app/routers/auth.py` (User model)
9. Modify: `app/routers/admin.py` (User model, reporter filter)
10. Modify: `app/routers/sarvam.py` (User model)
11. Modify: `app/routers/stories.py` (User model)
12. Modify: `app/main.py` (seed data with reviewer)

### Frontend (create/modify):
1. Create: `src/contexts/AuthContext.jsx`
2. Create: `src/components/ProtectedRoute.jsx`
3. Create: `src/pages/LoginPage.jsx`
4. Create: `src/pages/LoginPage.module.css`
5. Create: `src/extensions/TranscriptionMark.js`
6. Modify: `src/services/api.js` (auth headers, auth endpoints, llmChat)
7. Modify: `src/App.jsx` (AuthProvider, ProtectedRoute, LoginPage route)
8. Modify: `src/components/layout/Sidebar.jsx` (entitlements, user profile)
9. Modify: `src/pages/ReviewPage.jsx` (complete redesign)
10. Modify: `src/pages/ReviewPage.module.css` (complete redesign)
11. Modify: `src/i18n/locales/en.json` (auth + editor keys)
12. Modify: `src/i18n/locales/or.json` (auth + editor keys)
13. Modify: `package.json` (TipTap table extensions)
