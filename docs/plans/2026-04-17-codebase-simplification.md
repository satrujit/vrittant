# Codebase Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce cognitive load of the Vrittant codebase — every shipped feature preserved, every "giant" file (>600 LOC) under 400 LOC, one canonical pattern for cross-cutting concerns, no dead code.

**Architecture:** Phased, additive-then-subtractive.
1. **Dead-code sweep** first (fastest, lowest risk, smaller surface area for everything that follows).
2. **Conventions + helpers** next (one canonical way to scope-by-org and call the API; without this, splits would just redistribute the inconsistency).
3. **Surgical splits** next, leaf modules first so consumers don't get touched twice.
4. **Final structural cleanup** last (seed extraction, router mount loop, ARCHITECTURE.md).

Each phase ships as one or more reviewable commits on `develop` → auto-deploys to UAT → manual smoke → promote to `main`.

**Tech Stack:**
- Backend: FastAPI 0.115, SQLAlchemy 2, PostgreSQL, pytest 8.3 (60 tests baseline), respx for httpx mocks.
- Frontend: React 19 + Vite 6 + Tailwind 4 + shadcn/ui, Vitest (minimal coverage).
- Deploy: GitHub Actions → Cloud Run (api) + Firebase Hosting (panel). UAT = `develop`, prod = `main`.

**Source design:** [`docs/plans/2026-04-17-codebase-simplification-design.md`](2026-04-17-codebase-simplification-design.md). User approved 2026-04-17.

**Branch:** Work on `develop`. Push after each task. Promote to `main` only at end of each phase, not after every task.

**Hard constraints:**
- No new dependencies (Python or npm).
- No DB schema changes.
- No behavior changes — pure refactor + deletes.
- All 60 existing pytest cases must still pass after every commit.
- Manual UAT smoke after each phase: login, list stories, open ReviewPage, save edit, list editions, list buckets, render widgets page.

---

## Pre-flight (do once, before Phase 1)

### Task 0.1: Confirm clean baseline

**Files:** none

**Step 1: Verify on develop, in sync**
```bash
cd /Users/admin/Desktop/vrittant-monorepo
git checkout develop
git pull --ff-only
git status                        # must show clean tree
git log --oneline -5              # confirm e4a6e4c (design doc) is HEAD or near-HEAD
```
Expected: branch develop, up-to-date, no uncommitted changes.

**Step 2: Run full pytest baseline**
```bash
cd /Users/admin/Desktop/vrittant-monorepo/api
source .venv/bin/activate
python -m pytest -q
```
Expected: `60 passed` (the count locked in by the security-fix commit).

**Step 3: Frontend build sanity**
```bash
cd /Users/admin/Desktop/vrittant-monorepo/reviewer-panel
npx vite build
```
Expected: build succeeds, dist/ produced. (We will not deploy panel during refactor — this is just a smoke that imports resolve.)

**Step 4: Record baseline LOC for the giant files**
```bash
cd /Users/admin/Desktop/vrittant-monorepo
wc -l api/app/routers/admin.py api/app/routers/news_articles.py \
      api/app/routers/editions.py api/app/services/idml_generator.py \
      reviewer-panel/src/services/api.js \
      reviewer-panel/src/pages/ReviewPage.jsx \
      reviewer-panel/src/pages/BucketsPage.jsx \
      reviewer-panel/src/pages/WidgetsPage.jsx
```
Expected: matches the design-doc table (1650 / 756 / 680 / 806 / 795 / 1671 / 962 / 656).

If any step fails, **stop and investigate** — do not proceed into the refactor on a broken baseline.

---

## Phase 1 — Dead-code sweep

Goal: shrink surface area before any restructuring. Each delete is independent and trivially revertible.

### Task 1.1: Remove `firebase_admin_setup.py` (backend)

The module exposes `init_firebase()` (called once from `main.py`) and `verify_firebase_token()` (called nowhere). Auth is now MSG91 + JWT — Firebase Admin is vestigial. Confirmed by:
```bash
grep -rn "firebase_admin\|verify_firebase_token" api/app --include="*.py"
```
Only references are in `firebase_admin_setup.py` itself and `main.py`'s import.

**Files:**
- Delete: `api/app/firebase_admin_setup.py`
- Modify: `api/app/main.py:23-25` (remove import + `init_firebase()` call)
- Modify: `api/requirements.txt` (remove `firebase-admin` line)

**Step 1: Re-confirm zero usage outside the two known sites**
```bash
cd /Users/admin/Desktop/vrittant-monorepo
grep -rn "firebase_admin\|firebase_admin_setup\|verify_firebase_token\|init_firebase" \
  api/app --include="*.py"
```
Expected: only `api/app/firebase_admin_setup.py` lines and the two `api/app/main.py` lines (the import and the call). Anything else → **stop and investigate**.

**Step 2: Remove the file**
```bash
rm api/app/firebase_admin_setup.py
```

**Step 3: Edit `api/app/main.py`** — delete the two lines:
```python
# Initialize Firebase Admin SDK for ID token verification
from .firebase_admin_setup import init_firebase
init_firebase()
```
Use the Edit tool, exact match including the comment line above.

**Step 4: Remove `firebase-admin` from `api/requirements.txt`**

Use Edit tool to remove the line that pins `firebase-admin==...`.

**Step 5: Run tests + import-smoke**
```bash
cd api
source .venv/bin/activate
python -c "from app import main; print('import ok')"
python -m pytest -q
```
Expected: `import ok`, `60 passed`.

**Step 6: Commit**
```bash
git add api/app/main.py api/requirements.txt
git rm api/app/firebase_admin_setup.py
git commit -m "chore(api): remove vestigial Firebase Admin SDK init

Auth is MSG91 + JWT; verify_firebase_token() was never called and
init_firebase() did nothing useful. Drops firebase-admin dependency."
```

---

### Task 1.2: Remove `services/firebase.js` and `services/mockData.js` (panel)

`mockData.js`: `grep -rn "mockData" reviewer-panel/src` returns nothing → orphan.
`firebase.js`: imported once by `AuthContext.jsx` for an `auth.signOut()` call that runs at logout. Since auth is MSG91/JWT (`localStorage.removeItem('vr_token')` does the real work), the signOut call is a no-op safety belt. We delete the firebase module and inline-delete the import + the dead `try { auth.signOut(); }` line.

**Files:**
- Delete: `reviewer-panel/src/services/firebase.js`
- Delete: `reviewer-panel/src/services/mockData.js`
- Modify: `reviewer-panel/src/contexts/AuthContext.jsx:3` and `:43` (remove import + signOut call)
- Modify: `reviewer-panel/package.json` (remove `firebase` dependency)

**Step 1: Confirm only AuthContext uses firebase**
```bash
grep -rn "from.*services/firebase\|from 'firebase\|from \"firebase" \
  reviewer-panel/src --include="*.js" --include="*.jsx"
```
Expected: only `reviewer-panel/src/contexts/AuthContext.jsx:3` and the firebase.js file itself. Anything else → **stop**.

**Step 2: Confirm mockData has zero imports**
```bash
grep -rn "mockData" reviewer-panel/src --include="*.js" --include="*.jsx"
```
Expected: empty.

**Step 3: Edit `AuthContext.jsx`** — remove the `import { auth } from '../services/firebase';` line and the `try { auth.signOut(); } catch {}` line. Read the full surrounding logout function first to make sure no other reference remains.

**Step 4: Delete the files**
```bash
rm reviewer-panel/src/services/firebase.js reviewer-panel/src/services/mockData.js
```

**Step 5: Remove `firebase` from `reviewer-panel/package.json`** dependencies block (Edit tool, exact match on the `"firebase": "..."` line including trailing comma if present).

**Step 6: Reinstall + build**
```bash
cd reviewer-panel
rm -rf node_modules/.vite
npm install
npx vite build
```
Expected: install succeeds, build succeeds, no "Cannot resolve" errors.

**Step 7: Commit**
```bash
git add reviewer-panel/src/contexts/AuthContext.jsx reviewer-panel/package.json reviewer-panel/package-lock.json
git rm reviewer-panel/src/services/firebase.js reviewer-panel/src/services/mockData.js
git commit -m "chore(panel): remove unused Firebase auth + mockData

AuthContext used firebase.js only for a no-op signOut at logout; auth
is MSG91 + JWT, real logout is localStorage.removeItem. mockData.js
had zero importers."
```

---

### Task 1.3: Audit and delete orphan API endpoints

Find router endpoints that the panel never calls and that aren't called by the mobile app via documented routes. Mobile app is in a separate repo — be conservative: only delete endpoints with **no panel reference AND no plausible mobile use**. When in doubt, keep.

**Files:** any router under `api/app/routers/*.py` that has confirmed-orphan endpoints.

**Step 1: Build the list of endpoints the panel calls**
```bash
cd /Users/admin/Desktop/vrittant-monorepo
grep -rEn "fetch\(|apiFetch\(|`/[a-z]" reviewer-panel/src --include="*.js" --include="*.jsx" \
  | grep -oE "['\"\`]/[a-zA-Z0-9/_{}-]+" | sort -u > /tmp/panel-endpoints.txt
wc -l /tmp/panel-endpoints.txt
head -30 /tmp/panel-endpoints.txt
```

**Step 2: Build the list of endpoints the API exposes**
```bash
grep -rEn "@router\.(get|post|put|delete|patch)" api/app/routers --include="*.py" \
  | sed -E 's/.*@router\.[a-z]+\(["'"'"']([^"'"'"']+).*/\1/' | sort -u > /tmp/api-endpoints.txt
wc -l /tmp/api-endpoints.txt
```

**Step 3: Diff to find candidates**

Read both files. For each API endpoint not in the panel list, classify as:
- **Mobile-likely** (`/auth/*`, anything under `/stories/*` reporters submit, anything under `/reporters/me`): **KEEP**, do not delete.
- **Admin-only and panel-only** (anything in `routers/admin.py` not in panel list): candidate for delete.
- **Genuine orphan** (e.g. an old `/legacy/*` path, a debug endpoint, a duplicate): delete.

**Step 4: Produce a written audit comment**

Before any deletion, append the candidate list as a comment in the commit message. If the candidate list is empty or you're unsure, **commit nothing for this task** and move on. We will not speculatively delete.

**Step 5: For each confirmed orphan, delete the endpoint function and any helpers it uniquely uses**

Use Edit. After each delete:
```bash
cd api
source .venv/bin/activate
python -c "from app import main"
python -m pytest -q
```
Expected: import + 60 passed.

**Step 6: Commit (only if anything was deleted)**
```bash
git add api/app/routers
git commit -m "chore(api): remove orphan endpoints

Endpoints removed (no panel reference, no documented mobile call):
- <list>"
```

If nothing deleted, skip commit and note in PR/notes that audit found no orphans.

---

### Task 1.4: Audit Dockerfiles, scripts, env vars

**Files:** various.

**Step 1: List all Dockerfiles and shell scripts in repo**
```bash
cd /Users/admin/Desktop/vrittant-monorepo
find . -maxdepth 4 \( -name "Dockerfile*" -o -name "*.sh" \) \
  -not -path "*/node_modules/*" -not -path "*/.venv/*" -not -path "*/dist/*" \
  -not -path "*/.git/*"
```

**Step 2: For each, check if it's referenced from `.github/workflows/*.yml`, `cloudbuild*.yaml`, or `package.json` scripts**
```bash
grep -rn "<script-name>" .github/ widgets/cloudbuild* api/Dockerfile reviewer-panel/package.json 2>/dev/null
```

**Step 3: Delete only the ones with zero references**

Examples to specifically check (do not delete blindly — check first): any `*-renderer.*` artifact left from the iframe-renderer cleanup, any `deploy_*.sh` that's not in the CI workflows.

**Step 4: Commit (if anything deleted)**
```bash
git rm <files>
git commit -m "chore: remove unreferenced Dockerfiles/scripts

<list with one-line reason each>"
```

If nothing deletable, skip the commit.

---

### Task 1.5: Push Phase 1 to develop, smoke UAT

**Step 1: Push**
```bash
cd /Users/admin/Desktop/vrittant-monorepo
git push origin develop
```

**Step 2: Watch CI** — `gh run list --limit 3` and confirm the deploy-uat workflow completes green.

**Step 3: Manual UAT smoke** (panel: `https://vrittant-uat.web.app`)
- [ ] Login flow (MSG91 widget) succeeds
- [ ] Dashboard loads, no console errors
- [ ] AllStories → open one in ReviewPage → make a small edit → save
- [ ] Editions page loads
- [ ] Buckets page loads
- [ ] Widgets page renders at least one widget tile

If any step fails, **stop, fix, re-deploy** before moving to Phase 0.

**Step 4: Promote Phase 1 to prod**
```bash
git checkout main
git pull --ff-only
git merge --ff-only develop
git push origin main
git checkout develop
```
Watch deploy-prod workflow. Spot-check `https://vrittant-f5ef2.web.app` login.

---

## Phase 0 — Conventions + helpers

Goal: introduce one canonical helper per cross-cutting concern, before splitting. **No call sites change yet** — Phase 2 picks them up as it touches each file.

### Task 0.1: Add `api/app/utils/scope.py`

The recurring "fetch by id, filter by org, raise 404" pattern appears dozens of times. This was the exact pattern the security review showed was being missed in `editions.py`. We give it one home.

**Files:**
- Create: `api/app/utils/scope.py`
- Test: `api/tests/test_scope_helper.py`

**Step 1: Write the failing test**

Create `api/tests/test_scope_helper.py`:
```python
"""Tests for the org-scoping helper."""
import pytest
from fastapi import HTTPException
from app.models.story import Story
from app.utils.scope import get_owned_or_404
from .conftest import db_session  # adjust if conftest uses different name


def test_returns_object_when_org_matches(db_session):
    story = Story(
        id="s-1", organization_id="org-a", reporter_id="r-1",
        title="t", content_odia="c", status="draft",
    )
    db_session.add(story); db_session.commit()
    got = get_owned_or_404(db_session, Story, "s-1", "org-a")
    assert got.id == "s-1"


def test_raises_404_when_id_missing(db_session):
    with pytest.raises(HTTPException) as exc:
        get_owned_or_404(db_session, Story, "nope", "org-a")
    assert exc.value.status_code == 404


def test_raises_404_when_org_mismatch(db_session):
    story = Story(
        id="s-2", organization_id="org-a", reporter_id="r-1",
        title="t", content_odia="c", status="draft",
    )
    db_session.add(story); db_session.commit()
    with pytest.raises(HTTPException) as exc:
        get_owned_or_404(db_session, Story, "s-2", "org-b")
    # Must be 404, NOT 403 — leaking existence is the IDOR bug we're preventing.
    assert exc.value.status_code == 404
```

If `conftest.py` doesn't expose a `db_session` fixture in the form above, **first read `api/tests/conftest.py`** and adapt the import + fixture name to match what's actually there. Do not invent fixtures.

**Step 2: Run the test, confirm RED**
```bash
cd api
source .venv/bin/activate
python -m pytest tests/test_scope_helper.py -v
```
Expected: ImportError on `app.utils.scope` (module doesn't exist yet). That's the right failure.

**Step 3: Write the minimal helper**

Create `api/app/utils/scope.py`:
```python
"""Org-scoped fetch helper.

Use this anywhere you'd write `db.query(Model).filter(Model.id == id,
Model.organization_id == org_id).first()` followed by a 404. Centralizing
the pattern removes the IDOR risk of forgetting the org filter.
"""
from typing import Type, TypeVar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

T = TypeVar("T")


def get_owned_or_404(db: Session, model: Type[T], obj_id, org_id: str) -> T:
    """Fetch model by id within org, or raise 404.

    Returns 404 (not 403) on org mismatch — leaking existence is itself
    an IDOR signal.
    """
    obj = (
        db.query(model)
        .filter(model.id == obj_id, model.organization_id == org_id)
        .first()
    )
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    return obj
```

**Step 4: Run tests, confirm GREEN**
```bash
python -m pytest tests/test_scope_helper.py -v
python -m pytest -q
```
Expected: 3 new pass + 60 prior = 63 passed.

**Step 5: Commit**
```bash
git add api/app/utils/scope.py api/tests/test_scope_helper.py
git commit -m "feat(api): add get_owned_or_404 scope helper

Centralizes the 'fetch-by-id-and-org-or-404' pattern so we can't
forget the org filter (the IDOR class fixed in 289820a).
Returns 404 on org mismatch — never leak existence."
```

---

### Task 0.2: Add `reviewer-panel/src/services/http.js`

A thin `apiGet/apiPost/apiPut/apiDelete` over `fetch`, using the existing token + 401-redirect logic from `services/api.js`. Phase 2's `services/api.js` split will be the first consumer.

**Files:**
- Create: `reviewer-panel/src/services/http.js`
- Test: `reviewer-panel/src/test/http.test.js`

**Step 1: Write the failing test**

Create `reviewer-panel/src/test/http.test.js`:
```javascript
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from '../services/http';

const API_BASE = 'http://api.test';

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE', API_BASE);
  vi.stubGlobal('localStorage', {
    _s: {},
    getItem(k) { return this._s[k] ?? null; },
    setItem(k, v) { this._s[k] = String(v); },
    removeItem(k) { delete this._s[k]; },
  });
  globalThis.fetch = vi.fn();
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe('http wrapper', () => {
  it('apiGet sends GET with bearer token and returns JSON', async () => {
    localStorage.setItem('vr_token', 'tok');
    fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ x: 1 }) });
    const data = await apiGet('/foo');
    expect(data).toEqual({ x: 1 });
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/foo`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
      })
    );
  });

  it('apiPost sends JSON body', async () => {
    fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: true }) });
    await apiPost('/foo', { a: 1 });
    const [, opts] = fetch.mock.calls[0];
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ a: 1 });
  });

  it('throws ApiError with status on non-2xx', async () => {
    fetch.mockResolvedValue({
      ok: false, status: 422, statusText: 'Unprocessable',
      text: async () => '{"detail":"bad"}',
    });
    await expect(apiGet('/foo')).rejects.toMatchObject({
      name: 'ApiError', status: 422,
    });
  });

  it('returns null on 204', async () => {
    fetch.mockResolvedValue({ ok: true, status: 204 });
    expect(await apiDelete('/foo')).toBeNull();
  });
});
```

**Step 2: Run, confirm RED**
```bash
cd reviewer-panel
npx vitest run src/test/http.test.js
```
Expected: fail — module doesn't exist.

**Step 3: Write the minimal `services/http.js`**

Create `reviewer-panel/src/services/http.js`:
```javascript
/**
 * Thin HTTP wrapper around fetch — one place for auth header, base URL,
 * 401 redirect, error shape. Use these from every API module.
 */

const API_BASE = import.meta.env.VITE_API_BASE;
const TOKEN_KEY = 'vr_token';

export class ApiError extends Error {
  constructor(status, message, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

function authHeader() {
  const t = localStorage.getItem(TOKEN_KEY);
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function request(method, path, body) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new ApiError(401, 'Session expired');
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, `${res.status} ${res.statusText}`, text);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const apiGet    = (path)        => request('GET',    path);
export const apiPost   = (path, body)  => request('POST',   path, body);
export const apiPut    = (path, body)  => request('PUT',    path, body);
export const apiDelete = (path)        => request('DELETE', path);
```

**Step 4: Run, confirm GREEN**
```bash
npx vitest run src/test/http.test.js
```
Expected: 4 passed.

**Step 5: Build smoke**
```bash
npx vite build
```
Expected: build succeeds.

**Step 6: Commit**
```bash
git add reviewer-panel/src/services/http.js reviewer-panel/src/test/http.test.js
git commit -m "feat(panel): add http wrapper (apiGet/apiPost/apiPut/apiDelete)

One canonical fetch wrapper — auth header, base URL, 401 redirect,
ApiError shape. Phase 2 will rebuild services/api.js around this."
```

---

### Task 0.3: Write `docs/CONVENTIONS.md`

Short doc — ≤ 1 page. Captures the canonical patterns so future code uses them.

**Files:**
- Create: `docs/CONVENTIONS.md`

**Step 1: Write the file**

Use the Write tool to create `docs/CONVENTIONS.md` with these exact sections (titles bold, ~3-6 bullets each):

1. **Backend: routers** — one router per `routers/<thing>.py`. Mounted in `main.py`. Use a sub-package (`routers/<thing>/__init__.py` + sub-modules) when one file would exceed ~400 LOC.
2. **Backend: scoping by org** — always use `from app.utils.scope import get_owned_or_404`. Never write the manual filter pattern. Cross-org access returns 404, not 403.
3. **Backend: authed endpoints** — depend on `get_current_user` from `app.deps`. For org_admin-only endpoints, depend on `get_org_admin` (add this if it doesn't yet exist; check first).
4. **Backend: external HTTP** — use `httpx.AsyncClient` with explicit timeout. Never log response bodies (they may contain echoed credentials/OTPs/PII). Status code + endpoint name only.
5. **Backend: tests** — pytest, one test per behavior, use fixtures from `tests/conftest.py`. New tests must follow TDD (write failing test first; @superpowers:test-driven-development applies).
6. **Panel: API calls** — always go through `services/http.js` (`apiGet/apiPost/apiPut/apiDelete`). One ApiError shape, one 401 redirect path. Page-level `try/catch { setError(...) }` blocks should be a single error toast, not bespoke per page.
7. **Panel: forms + dialogs** — shadcn `Dialog` + react-hook-form. One pattern: `useForm` → `<form onSubmit={handleSubmit(onSave)}>` → submit calls API helper.
8. **Panel: widgets** — one renderer per file under `components/widgets/<Kind>.jsx`. The catalog mapping lives in `pages/WidgetsPage.jsx` only.
9. **Naming** — files in `kebab-case` for routes/pages, `PascalCase` for components, `snake_case` for Python.
10. **Commits** — Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`. One concern per commit.

Keep it short — no rationale paragraphs, just the rules. ~50 lines max.

**Step 2: Commit**
```bash
git add docs/CONVENTIONS.md
git commit -m "docs: add CONVENTIONS.md (one canonical pattern per concern)"
```

---

### Task 0.4: Push Phase 0 to develop, smoke UAT

Same as Task 1.5: push, watch CI, smoke UAT, promote to main.

---

## Phase 2 — Surgical splits

Each split is **one commit per giant file**, leaf-first. After every split:
1. Run full pytest (`60+ passed`).
2. Run `npx vite build`.
3. Push to develop, smoke UAT.
4. Only promote to main once the whole phase is done — too many small prod deploys is its own risk.

### Task 2.1: Split `reviewer-panel/src/services/api.js` (795 LOC)

Leaf module. Split by domain. The new layout:

```
reviewer-panel/src/services/
  http.js            (already created in Task 0.2)
  api/
    index.js         (re-exports everything for backward compat)
    cache.js         (the SWR cache helpers + _mergeDelta)
    stories.js
    editions.js
    reporters.js
    advertisers.js
    widgets.js
    buckets.js
    ...one file per resource group as identified by the existing section dividers in api.js
```

**Files:**
- Read fully: `reviewer-panel/src/services/api.js` (all 795 lines)
- Create: `reviewer-panel/src/services/api/index.js` and one file per domain group
- Delete (eventually): `reviewer-panel/src/services/api.js`
- Modify: nothing else — `index.js` re-exports the same names so all importers keep working

**Step 1: Inventory the existing exports**
```bash
grep -nE "^export (function|const|async function)" reviewer-panel/src/services/api.js
```
Note every exported name. The new layout must export the same set.

**Step 2: Identify section boundaries**

`api.js` has `// ── X ──` style dividers. Each becomes one file under `services/api/`.

**Step 3: Move groups, one at a time**

For each group:
1. Create `services/api/<group>.js`.
2. Move the functions verbatim. Replace the inline `apiFetch` (or whatever wrapper) with `apiGet/apiPost/apiPut/apiDelete` from `../http.js` — this is where Phase 0's helper starts paying off.
3. Re-export from `services/api/index.js` (`export * from './stories.js';`).
4. Build: `npx vite build`. Must pass.
5. Run tests: `npx vitest run`. Must pass.

Do this group-by-group, **not all at once**. After each group succeeds, the old `api.js` still has the rest — leave it intact until all groups moved.

**Step 4: Switch importers**

After all groups are moved and re-exported, importers in `pages/` and `components/` already use `from '../services/api'` — that resolves to `services/api/index.js` automatically (Vite resolution). No importer changes needed.

**Step 5: Delete the old `api.js`**
```bash
rm reviewer-panel/src/services/api.js
npx vite build
npx vitest run
```
Build + tests must pass. If anything breaks, the missing function is the new file.

**Step 6: Verify size targets**
```bash
wc -l reviewer-panel/src/services/api/*.js
```
Each new file should be < 200 LOC.

**Step 7: Commit**
```bash
git add reviewer-panel/src/services/api reviewer-panel/src/services
git rm reviewer-panel/src/services/api.js
git commit -m "refactor(panel): split services/api.js into per-domain modules

services/api.js (795 LOC) → services/api/{stories,editions,reporters,
advertisers,widgets,buckets,...}.js, re-exported from index.js.
All call sites unchanged (path resolves to api/index.js).
Each module now uses the apiGet/apiPost wrappers from services/http.js."
```

**Step 8: Push, smoke UAT**
```bash
git push origin develop
```
UAT smoke list (focus on API-heavy paths): login → dashboard → stories list → open a story → save edit → editions list → reporters list.

---

### Task 2.2: Split `api/app/routers/admin.py` (1650 LOC)

The biggest backend file. Split into a sub-package, one file per resource area.

**Target layout:**
```
api/app/routers/admin/
  __init__.py        (creates and mounts all sub-routers; exports `router` and `config_router` for main.py to import)
  dashboard.py
  reporters.py
  users.py
  advertisers.py
  config.py
  areas.py
  ...etc, one per logical group identified by existing comment dividers
```

**Files:**
- Read fully: `api/app/routers/admin.py`
- Create: `api/app/routers/admin/__init__.py` and one sub-module per group
- Delete: `api/app/routers/admin.py`
- `api/app/main.py` keeps its existing `from .routers import admin` and `app.include_router(admin.router)` + `app.include_router(admin.config_router)` — the new `admin/__init__.py` re-exposes both names

**Step 1: Identify section boundaries** — read `admin.py` and list the `# ── X ──` dividers. Each becomes one sub-module.

**Step 2: Identify which endpoints live on `router` vs `config_router`** — `main.py:78-79` shows both are mounted. Preserve the split exactly.

**Step 3: Read `api/app/routers/__init__.py` and `api/app/main.py`** — confirm exactly which names main.py imports from `admin`. The new package must export the same names.

**Step 4: Build the package skeleton first** — `__init__.py`:
```python
"""Admin endpoints, split by resource group.

Re-exports `router` and `config_router` for main.py."""
from fastapi import APIRouter

router = APIRouter()
config_router = APIRouter()  # mounts at /config or wherever main.py expects

from . import dashboard, reporters, users, advertisers, config, areas  # noqa: E402

# Each sub-module appends its routes to the right router via @router.get etc.
# Or: each sub-module exports its own sub-router and we include here:
# router.include_router(dashboard.router, prefix="/admin")
```

Pick whichever pattern is simpler given how `admin.py` currently structures things. Read `admin.py` first. Two patterns to choose from:

**A. Sub-modules share the same `router` object:** `__init__.py` creates `router`, sub-modules do `from . import router` then `@router.get(...)`. Simplest, no nested includes.

**B. Sub-modules each define their own sub-router, `__init__.py` includes them all:** more boilerplate but each file is independently testable.

**Pick A** unless `admin.py` has a clear reason to use B (different prefixes per group, etc.). If groups need different prefixes, A still works — just include `prefix="..."` on each `@router.get`.

**Step 5: Move endpoints group-by-group**

For each group:
1. Create `routers/admin/<group>.py`.
2. Move all endpoint functions for that group verbatim. Imports stay the same.
3. **Apply Phase 0 helper:** every place that does the manual "fetch by id, filter by org, raise 404" pattern, replace with `from ..utils.scope import get_owned_or_404` (note `..` because we're now in a sub-package). This is the only behavior-touching change permitted, and it's a noop refactor (the test in Task 0.1 confirms the helper raises the same 404).
4. After each group:
   ```bash
   cd api && source .venv/bin/activate
   python -c "from app import main"
   python -m pytest -q
   ```
   Must pass.

**Step 6: Delete old `admin.py`** once all groups moved + tests pass.
```bash
rm api/app/routers/admin.py
python -c "from app import main"
python -m pytest -q
```

**Step 7: Verify size targets**
```bash
wc -l api/app/routers/admin/*.py
```
Each sub-module < 400 LOC.

**Step 8: Commit**
```bash
git add api/app/routers/admin
git rm api/app/routers/admin.py
git commit -m "refactor(api): split admin.py into per-resource sub-modules

routers/admin.py (1650 LOC) → routers/admin/{dashboard,reporters,users,
advertisers,config,areas}.py. main.py imports unchanged: __init__.py
re-exposes router + config_router. All scope-by-org sites converted to
get_owned_or_404 helper (no behavior change, IDOR-safe by construction)."
```

**Step 9: Push, smoke UAT** — admin pages are heavy: SettingsPage, all admin tabs (Users, Org, MasterData), reporter list, areas. Click through every admin tab and create/edit/delete one of each.

---

### Task 2.3: Split `api/app/routers/news_articles.py` (756 LOC)

Router stays thin (HTTP shape only). All scrape + normalize logic moves to `services/news_scraper.py`.

**Target layout:**
- `api/app/routers/news_articles.py` (router endpoints only — < 200 LOC)
- `api/app/services/news_scraper.py` (scraping, parsing, normalization functions)

**Step 1: Read `routers/news_articles.py` fully.** Identify which functions are pure-business (scrape, parse, dedupe, classify) vs HTTP shape (request validation, response building, DB I/O).

**Step 2: TDD any extracted function** that doesn't have a test today. For each pure function moved to `services/news_scraper.py`, add a test in `api/tests/test_news_scraper.py` covering its happy-path + one edge case. Write test → confirm fail → move function → confirm pass.

**Step 3: Apply `get_owned_or_404`** anywhere the router fetches by id+org.

**Step 4: After move, run full suite + import smoke**
```bash
cd api && source .venv/bin/activate
python -c "from app import main"
python -m pytest -q
```

**Step 5: Commit**
```bash
git add api/app/routers/news_articles.py api/app/services/news_scraper.py api/tests/test_news_scraper.py
git commit -m "refactor(api): extract news scraping to services/news_scraper.py

routers/news_articles.py (756 LOC) → router (~200 LOC) + service module.
Router now only handles HTTP shape; scraping/parsing/dedup logic is
unit-testable in isolation."
```

**Step 6: Push, smoke UAT** — NewsFeed page, manually trigger a scrape if the panel exposes that.

---

### Task 2.4: Split `api/app/routers/editions.py` (680 LOC)

Already covered by Task 0.1's helper — apply it. Then split read endpoints, write endpoints, and the export-zip path into separate modules.

**Target layout:**
```
api/app/routers/editions/
  __init__.py        (re-exports `router`)
  read.py            (GET endpoints: list, detail, page detail)
  write.py           (POST/PUT/DELETE: create, assign_stories, add_story_to_page, etc.)
  export.py          (export_edition_zip and the zip-building helpers)
```

**Step 1-7:** same shape as Task 2.2.

**Special note:** the security fix in `289820a` already added per-story org checks in `assign_stories`, `add_story_to_page`, `export_edition_zip`. **Preserve those checks exactly.** Replace the manual filter pattern with `get_owned_or_404` — but where the security fix loops over a list of story_ids and checks each, keep that loop (the helper handles single-id; for bulk you can either loop the helper or write a `get_owned_bulk` variant — pick the loop, it's clearer).

**Step 8: Push, smoke UAT** — Editions page, create edition, assign stories from another reporter (still your org), try export-zip.

---

### Task 2.5: Split `reviewer-panel/src/pages/ReviewPage.jsx` (1671 LOC)

Largest panel file. Goal: a thin page component + extracted parts + a state hook.

**Target layout:**
```
reviewer-panel/src/pages/ReviewPage.jsx              (< 200 LOC, composition only)
reviewer-panel/src/components/review/
  ReviewHeader.jsx    (existing folder — see existing files like SocialTab.jsx, RelatedStoriesPanel.jsx)
  ReviewToolbar.jsx
  ReviewSidebar.jsx
  ReviewEditor.jsx
  useReviewState.js   (custom hook — all useState/useEffect/derived state lives here)
```

**Step 1: Read `ReviewPage.jsx` fully** in chunks (it's 1671 lines — read in 500-line offsets).

**Step 2: Identify the four visual regions** (header, toolbar, sidebar, editor body) by JSX structure. Each region's JSX moves to its own component.

**Step 3: Identify state ownership** — every `useState`, `useReducer`, `useEffect`, `useMemo`, `useCallback` at the top of `ReviewPage` is a candidate for `useReviewState`. The hook returns an object with all the state and setters; `ReviewPage` destructures and prop-drills (or uses Context if the depth gets ugly — but try prop-drilling first, it's simpler).

**Step 4: Extract one region at a time, build between each**
```bash
cd reviewer-panel
npx vite build
npx vitest run
```
Both must pass after every extraction.

**Step 5: Extract the hook last** — by then the page is just composition + state. Move state + effects into `useReviewState`, return what the regions need.

**Step 6: Verify sizes**
```bash
wc -l reviewer-panel/src/pages/ReviewPage.jsx \
      reviewer-panel/src/components/review/Review*.jsx \
      reviewer-panel/src/components/review/useReviewState.js
```
ReviewPage < 200, each region < 400, hook < 300.

**Step 7: Commit**
```bash
git add reviewer-panel/src/pages/ReviewPage.jsx reviewer-panel/src/components/review
git commit -m "refactor(panel): split ReviewPage.jsx into header/toolbar/sidebar/editor + useReviewState

ReviewPage.jsx (1671 LOC) → page (<200) + 4 region components + 1 hook.
No behavior change. Uses Phase 0 services/http.js for all API calls."
```

**Step 8: Push, smoke UAT** — this is the highest-blast-radius change. Smoke list:
- [ ] Open a story in ReviewPage
- [ ] Edit Odia content, save
- [ ] Edit translation, save
- [ ] Toggle status, save
- [ ] Open the related-stories panel
- [ ] Switch to Social tab
- [ ] Voice transcription button (if accessible)
- [ ] Navigate away and back — state resets correctly

---

### Task 2.6: Split `reviewer-panel/src/pages/BucketsPage.jsx` (962 LOC)

Currently combines bucket-list and bucket-detail. Split into two route components.

**Target layout:**
```
reviewer-panel/src/pages/buckets/
  BucketsListPage.jsx    (the list view)
  BucketDetailPage.jsx   (the detail view)
  index.js               (re-exports both, optional)
```

Or keep both at `pages/` root if `pages/` convention is flat — match what the rest of `pages/` does.

**Step 1: Read `BucketsPage.jsx`.** Find the conditional that renders list vs detail (likely `if (!selectedBucketId) return <List/>; else return <Detail/>;` or similar).

**Step 2: Update App.jsx routes** — instead of one `<Route path="/buckets" element={<BucketsPage/>}/>`, have:
```jsx
<Route path="/buckets" element={<BucketsListPage/>}/>
<Route path="/buckets/:id" element={<BucketDetailPage/>}/>
```

The detail route uses `useParams()` for the id instead of internal state. **Check if there are existing inbound links to `/buckets?bucket=X` style URLs** — if so, preserve query-string compatibility too, or add a redirect.

**Step 3: TDD any non-trivial helper functions** that come out of the split.

**Step 4: Commit**
```bash
git add reviewer-panel/src/App.jsx reviewer-panel/src/pages/buckets reviewer-panel/src/pages/BucketsPage.jsx
git commit -m "refactor(panel): split BucketsPage into list + detail route components

BucketsPage.jsx (962 LOC) → BucketsListPage + BucketDetailPage, each
its own route. Detail uses useParams instead of state-driven view switch."
```

**Step 5: Push, smoke UAT** — list, click into one, edit, navigate back, deep-link to a bucket detail URL.

---

### Task 2.7: Split `reviewer-panel/src/pages/WidgetsPage.jsx` (656 LOC)

One renderer per file under `components/widgets/`, page becomes a thin grid + CATALOG mapping.

**Target layout:**
```
reviewer-panel/src/components/widgets/
  AirQuality.jsx
  ChessPuzzle.jsx
  ...one file per widget kind (match the kinds in widgets/widgets_core/ on backend)
  index.js             (CATALOG: { widget_kind: Component } object)
reviewer-panel/src/pages/WidgetsPage.jsx   (< 200 LOC: fetch list, map kind→Component, render grid)
```

**Step 1: Read `WidgetsPage.jsx`.** The catalog is probably already a switch-statement or object literal — it just renders inline.

**Step 2: For each widget kind, extract its renderer to its own file.** Each file exports a default React component that takes `{ data }` (or whatever the existing prop shape is) and returns JSX.

**Step 3: Build `components/widgets/index.js`:**
```javascript
import AirQuality from './AirQuality.jsx';
// ...
export const CATALOG = {
  air_quality: AirQuality,
  // ...
};
```

**Step 4: Page becomes:**
```jsx
import { CATALOG } from '../components/widgets';
// fetch widgets, then:
{widgets.map(w => {
  const C = CATALOG[w.kind];
  return C ? <C key={w.id} data={w.data}/> : null;
})}
```

**Step 5: Build + test + commit**
```bash
npx vite build && npx vitest run
git add reviewer-panel/src/pages/WidgetsPage.jsx reviewer-panel/src/components/widgets
git commit -m "refactor(panel): one-renderer-per-file under components/widgets/

WidgetsPage.jsx (656 LOC) → page (<200) + 30+ tiny renderer files +
CATALOG mapping. New widget kinds = add one file + one CATALOG entry."
```

**Step 6: Push, smoke UAT** — widgets page, scroll through every kind, confirm none render blank/broken.

---

### Task 2.8: Split `api/app/services/idml_generator.py` (806 LOC)

InDesign Markup Language generator — split per section.

**Target layout:**
```
api/app/services/idml/
  __init__.py        (re-exports the public `generate(...)` orchestrator)
  header.py
  paragraphs.py
  images.py
  package.py         (zip + manifest)
```

**Step 1: Read `idml_generator.py`.** Identify section-builder functions: `_build_header`, `_render_paragraphs`, `_pack_images`, `_finalize_zip`, etc. (Names approximate — read the actual file.)

**Step 2: There IS an existing test** — `api/tests/test_idml_export.py`. **Run it first to lock baseline:**
```bash
cd api && source .venv/bin/activate
python -m pytest tests/test_idml_export.py -v
```
Note exact pass count.

**Step 3: Move sections one at a time.** After each move, re-run the IDML test. It must stay green.

**Step 4: `__init__.py` exposes `generate`** — the orchestrator. Importers in routers (probably `editions.py` or its split) keep doing `from app.services.idml_generator import generate` — make `idml_generator.py` a shim that does `from .idml import generate` and exports it, OR rename imports. Pick the shim if there are many importers.

Confirm importer count first:
```bash
grep -rn "from.*idml_generator\|import idml_generator" api/app --include="*.py"
```
- ≤ 2 importers: change them, delete `idml_generator.py`.
- > 2 importers: keep `idml_generator.py` as a 3-line shim that re-exports from `app.services.idml`.

**Step 5: Verify sizes + tests**
```bash
wc -l api/app/services/idml/*.py
python -m pytest -q
```

**Step 6: Commit**
```bash
git add api/app/services/idml api/app/services/idml_generator.py api/app/routers
git commit -m "refactor(api): split idml_generator into per-section package

services/idml_generator.py (806 LOC) → services/idml/{header,paragraphs,
images,package}.py + __init__.py orchestrator. test_idml_export.py
unchanged + still green."
```

**Step 7: Push, smoke UAT** — trigger an edition export-zip from the panel, verify the IDML file in the zip opens in InDesign (or matches a known-good byte hash if you have one).

---

### Task 2.9: End of Phase 2 — promote to main

After all 8 splits land on develop and UAT smoke passes:
```bash
git checkout main
git pull --ff-only
git merge --ff-only develop
git push origin main
git checkout develop
```
Watch deploy-prod CI. Spot-check prod login + open one ReviewPage.

---

## Phase 3 — Final structural cleanup

### Task 3.1: Move `seed_data()` out of `main.py`

`main.py` lines ~95–245 hold the `seed_data()` function (dev-only org/user/config seeding). It runs at import time when `ENV != "prod"`. Move to a script.

**Files:**
- Create: `api/scripts/seed_dev.py`
- Modify: `api/app/main.py` (delete `seed_data` definition + the `if settings.ENV != "prod": seed_data()` call; replace with a one-line dynamic import gated on env)

**Step 1: Create `api/scripts/seed_dev.py`** with the exact `seed_data` body (and its imports), wrapped:
```python
"""Seed dev orgs/users/configs. Called from main.py at startup when ENV != prod."""
from app.database import SessionLocal
from app.models.user import User, Entitlement
from app.models.organization import Organization
from app.models.org_config import (
    OrgConfig, DEFAULT_CATEGORIES, DEFAULT_PUBLICATION_TYPES,
    DEFAULT_PAGE_SUGGESTIONS, DEFAULT_PRIORITY_LEVELS,
)


def seed_data():
    db = SessionLocal()
    try:
        # ... exact body from main.py ...
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
```

**Step 2: In `api/app/main.py`** — delete the entire `def seed_data(): ...` block. Replace the trailing `if settings.ENV != "prod": seed_data()` with:
```python
if settings.ENV != "prod":
    from scripts.seed_dev import seed_data
    seed_data()
```
(Adjust import path to whatever resolves — may need `sys.path` munging or a relative import depending on how `scripts/` is laid out. Easier alternative: put `seed_dev.py` under `api/app/scripts/` and use `from .scripts.seed_dev import seed_data`.)

**Step 3: Test**
```bash
cd api && source .venv/bin/activate
python -c "from app import main"
python -m pytest -q
```

**Step 4: Commit**
```bash
git add api/app/main.py api/app/scripts/seed_dev.py  # (or wherever)
git commit -m "refactor(api): extract seed_data from main.py to scripts/seed_dev

main.py drops ~150 lines. Behavior preserved: still seeds when
ENV != prod; can also be invoked manually via python -m app.scripts.seed_dev."
```

---

### Task 3.2: Tighten `routers/__init__.py` + `main.py` mount loop

Currently `main.py` has 12 hand-written `app.include_router(...)` lines. Replace with a loop over a registry in `routers/__init__.py`.

**Files:**
- Modify: `api/app/routers/__init__.py`
- Modify: `api/app/main.py`

**Step 1: In `api/app/routers/__init__.py`:**
```python
"""All routers, exposed as a single mount-table for main.py."""
from . import (
    admin, auth, editions, files, layout_ai, layout_templates,
    news_articles, sarvam, speaker, stories, templates, widgets,
)

# (router, prefix, tags) — main.py loops this and mounts each.
ROUTERS = [
    (admin.router,         None,        None),
    (admin.config_router,  None,        None),
    (editions.router,      None,        None),
    (auth.router,          "/auth",     ["auth"]),
    (stories.router,       "/stories",  ["stories"]),
    (files.router,         "/files",    ["files"]),
    (sarvam.router,        None,        ["sarvam"]),
    (templates.router,     None,        None),
    (layout_templates.router, None,     None),
    (layout_ai.router,     None,        None),
    (news_articles.router, None,        None),
    (speaker.router,       None,        ["speaker"]),
    (widgets.router,       None,        None),
]
```

**Step 2: In `api/app/main.py`** — replace the 12 `app.include_router` lines with:
```python
from .routers import ROUTERS

for router, prefix, tags in ROUTERS:
    kwargs = {}
    if prefix: kwargs["prefix"] = prefix
    if tags:   kwargs["tags"] = tags
    app.include_router(router, **kwargs)
```

**Step 3: Smoke**
```bash
cd api && source .venv/bin/activate
python -c "from app import main; print(len(main.app.routes))"
python -m pytest -q
```
Route count should be the same as before (note the count first, before the change, and compare).

**Step 4: Commit**
```bash
git add api/app/routers/__init__.py api/app/main.py
git commit -m "refactor(api): mount routers from a registry instead of 12 manual lines"
```

---

### Task 3.3: Add `docs/ARCHITECTURE.md`

Single page. Goal: a new contributor can find any feature's code path within 30 seconds.

**Files:**
- Create: `docs/ARCHITECTURE.md`

**Step 1: Write the file** with these sections:

1. **Overview** (3 sentences) — what Vrittant is, who uses it, what the panel does.
2. **Repo layout** — directory tree, two levels deep, with one-line description per top-level folder:
   ```
   api/                FastAPI backend
     app/routers/      one module per resource group; admin/ is a sub-package
     app/services/     external integrations + pure business logic
     app/models/       SQLAlchemy ORM models
     app/utils/        scope.py, tz.py — pure helpers
     tests/            pytest, 60+ cases, run with `pytest -q`
   reviewer-panel/     React + Vite + Tailwind 4 + shadcn/ui editor panel
     src/pages/        one route per file; thin composition only
     src/components/   reusable UI; widgets/, review/, settings/, etc.
     src/services/     http.js (fetch wrapper) + api/ (per-domain modules)
     src/contexts/     AuthContext only
   widgets/            standalone Cloud Run Job that scrapes widget data into Postgres
   docs/               CONVENTIONS.md, ARCHITECTURE.md, plans/
   ```
3. **Data flow (ASCII diagram)** — Reporter mobile → API stories → DB → Reviewer panel → API stories edit → DB → IDML export.
4. **Auth path** — MSG91 widget → `/auth/msg91-login` → JWT → `Authorization: Bearer` header → `get_current_user` dep.
5. **Deploy** — push develop → UAT (auto), push main → prod (auto), via `.github/workflows/`.
6. **Where to find X (5 examples)** — "Adding a new admin tab", "Adding a new widget", "Adding a new endpoint", "Changing the seed data", "Editing translations".

Keep it < 150 lines. Link to `CONVENTIONS.md` for the rules.

**Step 2: Commit**
```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add ARCHITECTURE.md (single-page overview)"
```

---

### Task 3.4: Push Phase 3 to develop, smoke, promote to main

Same as previous phases. Then this plan is done.

---

## Done criteria (checklist)

- [ ] `wc -l api/app/routers/admin.py` reports "no such file" (it's now `routers/admin/`)
- [ ] `wc -l reviewer-panel/src/pages/ReviewPage.jsx` < 200
- [ ] `wc -l reviewer-panel/src/services/api.js` reports "no such file"
- [ ] All 8 originally-giant files now < 400 LOC each (or split into a sub-package)
- [ ] `pytest -q` reports 60+ passed (60 baseline + 3 from `test_scope_helper.py` minimum, plus any added during Task 2.3 / 2.6)
- [ ] `npx vite build` succeeds
- [ ] No new entries in `requirements.txt` or `package.json` dependencies (only deletions)
- [ ] `docs/CONVENTIONS.md` exists, < 1 page
- [ ] `docs/ARCHITECTURE.md` exists, < 150 lines
- [ ] UAT smoke passes after every phase
- [ ] Prod deploy of final state passes smoke (login + open one ReviewPage)

## What this plan does NOT touch

- Any other security finding from the audit (rate limiting, JWT-in-URL, python-jose CVE, SVG-XSS, SSRF, dev OTP bypass) — separate effort.
- DB schema. No migrations.
- Dependency upgrades (FastAPI, React, Tailwind major versions).
- The mobile app (different repo).
- The widgets/ standalone fetcher — it's already small and well-isolated.

## Rollback

Each phase is one or more independent commits. To revert any single split:
```bash
git revert <commit-sha>
git push origin develop
```
UAT auto-deploys the revert. Promote to main once verified. Because each commit only restructures (no behavior change), reverts are safe — they only un-restructure.
