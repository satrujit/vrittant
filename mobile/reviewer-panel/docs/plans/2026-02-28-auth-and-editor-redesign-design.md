# Auth System & Editor Redesign — Design Document

**Date:** 2026-02-28
**Status:** Approved

## Overview

Two-phase upgrade to the Vrittant reviewer panel:
- **Phase 1:** OTP-based authentication with user types and page-level entitlements
- **Phase 2:** ReviewPage redesign with voice-first editing and AI-powered text manipulation

---

## Phase 1: Authentication & Authorization

### Database Schema

**User table** (replaces Reporter):

| Column       | Type              | Notes                              |
|--------------|-------------------|------------------------------------|
| id           | String (UUID)     | PK                                 |
| name         | String            | Required                           |
| phone        | String            | Unique, indexed, for OTP           |
| email        | String            | Optional                           |
| user_type    | String            | `reporter` / `reviewer` / `admin`  |
| area_name    | String            | Optional (for reporters)           |
| organization | String            | Optional                           |
| is_active    | Boolean           | Default true                       |
| created_at   | DateTime          | Auto                               |
| updated_at   | DateTime          | Auto                               |

**Entitlement table**:

| Column   | Type                | Notes                                                                 |
|----------|---------------------|-----------------------------------------------------------------------|
| id       | Integer             | PK, auto-increment                                                    |
| user_id  | String (FK → User)  | Required                                                              |
| page_key | String              | `dashboard`, `stories`, `review`, `editions`, `reporters`, `social_export` |

One row per page a user can access.

### Backend Changes

1. Rename `Reporter` model → `User` model, add `email`, `user_type` columns
2. Create `Entitlement` model
3. Update `create_access_token` to include `user_type` in JWT payload
4. Create `get_current_user` dependency (replaces `get_current_reporter`)
5. Update `/auth/request-otp` and `/auth/verify-otp` to use User table
6. Add entitlements to `/auth/me` response
7. Protect admin endpoints with JWT + user_type check
8. Update Sarvam endpoints to accept any authenticated user
9. Update all existing references from Reporter → User
10. Alembic migration for schema changes
11. Seed data: test reviewer account with full entitlements

### Frontend Changes

1. `LoginPage` component: phone input → OTP input → JWT stored in localStorage
2. `AuthContext` provider: holds current user, token, entitlements, login/logout methods
3. `ProtectedRoute` wrapper: redirects to login if no token, checks entitlements
4. Update `api.js`: add Authorization header to all requests
5. Update `AppLayout`: conditionally show nav items based on entitlements
6. i18n keys for login page strings

### Auth Flow

```
1. User enters phone number on LoginPage
2. POST /auth/request-otp { phone }
3. User enters OTP (dev: 123456)
4. POST /auth/verify-otp { phone, otp }
5. Response: { access_token, token_type, user }
6. Token stored in localStorage, AuthContext updated
7. App renders with entitlement-filtered navigation
```

---

## Phase 2: ReviewPage Redesign

### Voice Dictation Mode

- Mic button in toolbar toggles dictation mode
- Web Speech API with `lang: 'or-IN'`, `continuous: true`, `interimResults: true`
- Interim transcript inserted inline at cursor as custom TipTap `TranscriptionMark` (orange #FA6C38)
- Rest of editor text gets `opacity: 0.4` (muted) via CSS class on editor wrapper
- Final transcript: mark removed, text becomes normal, muted state clears
- Works for both headline (via separate input handler) and body editor
- Voice indicator: "ସିଧା ଲିପିବଦ୍ଧ" with pulsing red dot

### AI Sparkle Mode

- When text is selected in editor, mic button changes to sparkle icon
- Click sparkle → enters command mode → mic starts recording
- User speaks instruction (e.g., "make formal", "summarize", "translate")
- Speech → text via Web Speech API
- API call: `POST /api/llm/chat` with JWT auth
  - System prompt: "You are an Odia language editor. Modify the following text as instructed. Return only the modified text in the same language."
  - User message: `"Instruction: {spoken_command}\n\nText to modify:\n{selected_text}"`
  - Model: `sarvam-m`
- Response replaces selected text in editor
- Loading spinner shown during API call

### Rich Text Enhancements

New TipTap extensions:
- `@tiptap/extension-table`
- `@tiptap/extension-table-row`
- `@tiptap/extension-table-cell`
- `@tiptap/extension-table-header`

Toolbar additions: Insert Table button, add/delete row/column controls

### UI Modernization

- Bottom action bar (mobile-inspired): advanced settings gear, attachment, sparkle/mic, save
- Top area: category + status chips (compact tags)
- Cleaner visual separation between editor and sidebar
- Floating sparkle button near text selection
- Recording indicator with animated pulse

### Dependencies to Install

```
npm install @tiptap/extension-table @tiptap/extension-table-row @tiptap/extension-table-cell @tiptap/extension-table-header
```

---

## File Impact Summary

### Backend (`newsflow-api/`)
- `app/models/reporter.py` → rename to `user.py`, update model
- `app/models/__init__.py` → update imports
- `app/schemas/` → add user schemas, entitlement schemas
- `app/routers/auth.py` → update for User model
- `app/routers/admin.py` → add JWT protection
- `app/routers/sarvam.py` → accept any authenticated user
- `app/deps.py` → add `get_current_user` dependency
- `app/main.py` → update router imports, seed data

### Frontend (`reviewer-panel/`)
- New: `src/pages/LoginPage.jsx` + `LoginPage.module.css`
- New: `src/contexts/AuthContext.jsx`
- New: `src/components/ProtectedRoute.jsx`
- Modified: `src/services/api.js` — auth headers, login/OTP endpoints
- Modified: `src/App.jsx` — auth provider, protected routes
- Modified: `src/components/layout/AppLayout.jsx` — entitlement-filtered nav
- Modified: `src/pages/ReviewPage.jsx` — complete redesign
- Modified: `src/pages/ReviewPage.module.css` — new styles
- Modified: `src/i18n/locales/en.json` + `or.json` — new keys
- Modified: `package.json` — new TipTap extensions
