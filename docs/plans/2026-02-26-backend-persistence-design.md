# Backend + Persistence + Bug Fix Design

**Date:** 2026-02-26
**Goal:** Fix text duplication bug, build FastAPI backend with auth + story CRUD, wire Flutter app to backend.

---

## 1. Bug Fix: Text Duplication

**Root cause:** `create_news_provider.dart:266-272` appends each STT WebSocket segment to `liveTranscript`. Sarvam sends cumulative partial transcripts within a VAD window, so appending causes duplication.

**Fix:** Track `_committedTranscript` (finalized VAD segments) separately from live partial. Each incoming `type: 'data'` message replaces the live partial. On VAD-end event, commit the partial to `_committedTranscript` and reset live partial. The displayed `liveTranscript` = `_committedTranscript + livePartial`.

---

## 2. FastAPI Backend

**Location:** `/Users/admin/Desktop/newsflow-api/`
**Stack:** FastAPI, SQLAlchemy, SQLite, Pydantic, python-jose (JWT)

### Data Models

**Reporter:**
- `id` (UUID, PK)
- `name` (str)
- `phone` (str, unique)
- `area_name` (str) — e.g. "Bhubaneswar", "Cuttack"
- `organization` (str) — e.g. "Dharitri News Network"
- `is_active` (bool, default true)
- `created_at`, `updated_at` (datetime)

**NewsStory:**
- `id` (UUID, PK)
- `reporter_id` (FK → Reporter)
- `headline` (str)
- `category` (str, nullable) — AI-inferred
- `location` (str, nullable) — AI-inferred
- `paragraphs` (JSON) — `[{id, text, photo_path, created_at}]`
- `status` (enum: draft | submitted | approved | published | rejected)
- `submitted_at` (datetime, nullable)
- `created_at`, `updated_at` (datetime)

**OTPRequest:**
- `id` (int, PK)
- `phone` (str)
- `otp_code` (str) — hardcoded "123456" for dev
- `expires_at` (datetime)
- `is_used` (bool)

### API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/auth/request-otp` | No | Send OTP (hardcoded for dev) |
| POST | `/auth/verify-otp` | No | Verify OTP → return JWT + reporter profile |
| GET | `/auth/me` | Yes | Get current reporter profile |
| POST | `/stories` | Yes | Create new story (draft) |
| PUT | `/stories/{id}` | Yes | Update story (auto-save draft) |
| POST | `/stories/{id}/submit` | Yes | Submit story for review |
| GET | `/stories` | Yes | List reporter's stories (default: last 5 or today's) |
| GET | `/stories/{id}` | Yes | Get single story |
| POST | `/stories/{id}/photos` | Yes | Upload photo |

### Auth Flow
1. Reporter enters phone number → `POST /auth/request-otp` (hardcoded OTP "123456")
2. Reporter enters OTP → `POST /auth/verify-otp` → returns JWT (30-day expiry) + reporter profile
3. JWT stored in SharedPreferences. On app launch, if JWT exists and not expired → auto-login via `GET /auth/me`
4. If JWT expired → redirect to login

### Seed Data
Pre-create a dummy reporter:
- Name: "Satrajit Mohapatra"
- Phone: "+919876543210"
- Area: "Bhubaneswar"
- Organization: "Dharitri News Network"

---

## 3. Flutter App Changes

### New: Login Screen
- Phone number field → "Get OTP" button → OTP field → "Verify" button
- On success: store JWT in SharedPreferences, navigate to home
- Auto-login: check for stored JWT on app launch

### New: AuthNotifier (Riverpod)
- `login(phone, otp)` → verify OTP, store JWT
- `logout()` → clear JWT, navigate to login
- `autoLogin()` → check stored JWT, fetch profile
- State: `AuthState(reporter, token, isLoading, error)`

### New: StoriesNotifier (Riverpod)
- `fetchStories()` → `GET /stories` (last 5 or today's)
- `createStory()` → `POST /stories` → returns story ID
- `updateStory(id, state)` → `PUT /stories/{id}` (called on auto-save)
- `submitStory(id)` → `POST /stories/{id}/submit`
- State: `StoriesState(stories, isLoading, error)`

### Modified: Home Screen
- Header: reporter name + area (from AuthNotifier)
- Body: list of stories — drafts pinned to top, then submitted/approved/rejected
- Each card shows: headline (or "Untitled"), status badge, paragraph count, time ago
- Tap card → opens notepad with that story loaded
- FAB or "+" nav button → creates new story

### Modified: NotepadNotifier
- On create: call `storiesNotifier.createStory()` to get server ID
- On every change (paragraph add/edit/delete, headline change): auto-save via `storiesNotifier.updateStory(id, state)`
- On submit: show confirmation dialog → call `storiesNotifier.submitStory(id)` → navigate to home
- When offline: disable mic button (STT needs network), allow typing only

### Modified: Router
- Add `/login` route
- Add auth guard: if no JWT → redirect to `/login`
- `/create` now accepts optional `?storyId=` param to load existing story

### New Dependencies
- `dio` — HTTP client
- `shared_preferences` — JWT + simple local cache

---

## 4. What's NOT in This Phase

- Real SMS OTP integration (hardcoded for now)
- Admin/editor dashboard for approving stories
- Photo upload to server (just local paths for now)
- Offline-first sync (require network for all operations)
- Push notifications
- SIM selection / auto-fetch OTP
