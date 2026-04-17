# Codebase Simplification — Design

**Date:** 2026-04-17
**Status:** Approved (user)

## Goal

Reduce the cognitive load of the codebase while keeping every shipped feature
intact. Target audience: a developer (or future-me) who should be able to
read this codebase end-to-end in an afternoon.

## Pain points (in user's stated priority order)

1. **Files are too big** — `ReviewPage.jsx` (1.7k LOC), `admin.py` (1.6k),
   `BucketsPage.jsx` (962), `idml_generator.py` (806), `services/api.js` (795).
   Hard to navigate, hard to grep, hard to review.
2. **Inconsistent patterns** — same cross-cutting concerns done multiple
   ways: org scoping, error handling, API calls, form/dialog wiring.
3. **Dead/half code** mixed with live code — e.g. `firebase_admin_setup.py`
   (vestigial, surfaced in security review), unclear if `mockData.js` is
   still wired, vestigial Firebase Auth client, possibly orphan endpoints
   the panel no longer calls.
4. **End-to-end readability** — there is no `ARCHITECTURE.md` or
   `CONVENTIONS.md`; structure has to be reverse-engineered.

## Approach: "Patterns first, then surgical split"

Chosen over (a) parallel rewrite — too risky given the live production
state — and (b) delete-only — only addresses pain #3.

Phased, each phase shipped as one or more reviewable commits on `develop`,
verified on UAT, then promoted to `main`.

### Phase 0 — `CONVENTIONS.md` + helpers (single commit, no behavior change)

Establish *one* canonical way to do the recurring stuff. Without this step,
later splits would just redistribute the inconsistency.

- `api/app/utils/scope.py` — `get_owned_or_404(db, Model, id, org_id)`
  helper that replaces the dozens of "fetch by id, filter by org, raise 404"
  blocks (and which the security review showed was being missed).
- `reviewer-panel/src/services/http.js` — `apiGet/apiPost/apiPut/apiDelete`
  wrappers around `fetch`, with one error → toast pipe. Every page-level
  `try/catch { setError(...) }` block disappears.
- `docs/CONVENTIONS.md` — short doc (≤ 1 page) covering: how routers are
  organized, how to add an authed endpoint, how to scope by org, the
  shadcn-Dialog + RHF form pattern, the "one widget renderer per file" rule.

### Phase 1 — Dead-code sweep (single commit, deletions only)

Audit + delete:
- `api/app/firebase_admin_setup.py` (vestigial — never called).
- `firebase-admin` from `requirements.txt` if Phase-0 pass confirms no use.
- `reviewer-panel/src/services/firebase.js` and `services/mockData.js` if
  not imported anywhere live.
- Any router endpoints not referenced from the panel (sweep both
  `services/api.js` and any direct `fetch(...)` calls).
- Dead `pages/` and `components/` files (those not imported by `App.jsx`
  or any router).
- Stale `Dockerfile`s, scripts, env vars confirmed unused.

Each deletion is independent — small commit, easy to revert if it breaks.

### Phase 2 — Surgical splits (one commit per giant file, in dep order)

Apply the Phase-0 patterns as we go. Order chosen so leaf modules move
first (their consumers don't have to be touched twice):

1. `services/api.js` (795) → `services/api/{stories,editions,reviewers,
   advertisers,widgets,...}.js` re-exported from `services/api/index.js`.
2. `routers/admin.py` (1650) → split into a package: `routers/admin/
   {dashboard,reporters,users,advertisers,config,areas}.py` with one
   sub-router per file, mounted in a single `__init__.py`.
3. `routers/news_articles.py` (756) → router stays thin; move scrape +
   normalize logic to `services/news_scraper.py`.
4. `routers/editions.py` (680) → split read endpoints, write endpoints,
   and export-zip into separate sub-modules.
5. `pages/ReviewPage.jsx` (1671) → extract `ReviewHeader`, `ReviewToolbar`,
   `ReviewSidebar`, `ReviewEditor`; move state into `useReviewState` hook.
6. `pages/BucketsPage.jsx` (962) → split bucket-list and bucket-detail
   into separate route components.
7. `pages/WidgetsPage.jsx` (656) → one renderer per file under
   `components/widgets/`; page becomes a thin grid + CATALOG mapping.
8. `services/idml_generator.py` (806) → split per-section: `header.py`,
   `paragraphs.py`, `images.py`, `package.py`. Single `generate()` orchestrator.

### Phase 3 — Final structural cleanup

- Move `seed_data()` out of `main.py` into `scripts/seed_dev.py`; call
  from `main.py` only when `ENV != "prod"` (current behavior preserved).
- Tighten `routers/__init__.py` — single import, single mount loop in
  `main.py` (replaces the 12-line manual `app.include_router(...)` block).
- Add `docs/ARCHITECTURE.md` — single page: directory tree + one paragraph
  per top-level module + ASCII data-flow diagram.

## Out of scope

- Other security findings from the audit (rate limiting, JWT-in-URL,
  python-jose CVE, SVG-XSS, SSRF) — separate effort.
- Database schema changes.
- Dependency upgrades (FastAPI, React, Tailwind major bumps).
- Mobile app (different repo).

## Risk + rollback

- Each commit is independent and shippable on its own.
- After each commit lands on `develop`, UAT auto-deploys; smoke-test there
  before promoting to `main`.
- Backend has 60 pytest cases (incl. the 9 security tests added today);
  CI runs on every push and blocks deploy on failure.
- Panel has minimal automated tests — depend on manual UAT smoke after
  each Phase-2 split.

## Success criteria

- All 8 giant files (the table above) drop below 400 LOC each.
- No new dependencies introduced.
- All 60 existing tests still pass; no functional regression observed in
  manual UAT smoke.
- `CONVENTIONS.md` and `ARCHITECTURE.md` exist and are accurate.
- A new contributor can find any feature's code path within 30 seconds via
  `ARCHITECTURE.md` + filename.
