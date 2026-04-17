# Vrittant Architecture

Single-page tour of the codebase. For the rules of the road (router shape, scoping,
forms, naming, commits), see [CONVENTIONS.md](./CONVENTIONS.md).

## 1. Overview

Vrittant is an editorial review and layout panel for Odia-language newspapers. Reporters
submit stories from a mobile app; sub-editors and org admins use the panel to review,
translate, place stories on a page, and export print-ready IDML. The system is one
FastAPI backend, one React panel, and a separate widget-data scraper that feeds
non-story content (weather, sports, markets, etc.) into the same database.

## 2. Repo layout

```
api/                       FastAPI backend (Cloud Run)
  app/main.py              ~88 LOC bootstrap; mounts routers from a registry
  app/routers/             one module per resource group
    admin/                 sub-package: org/users/reporters/dashboard/leaderboard/...
    editions/              sub-package: read / write / export (IDML)
    auth.py stories.py widgets.py news_articles.py templates.py
    layout_templates.py layout_ai.py sarvam.py speaker.py files.py
  app/services/            external integrations + pure business logic
    idml/                  IDML generator, split per page section
    msg91.py news_scraper.py openai_client.py storage.py
  app/models/              SQLAlchemy ORM models, one file per table
  app/utils/               scope.py (get_owned_or_404), tz.py (timezone helpers)
  app/scripts/seed_dev.py  dev seed data, invoked manually
  tests/                   pytest, run with `pytest -q`
reviewer-panel/            React + Vite + Tailwind 4 + shadcn/ui editor panel
  src/pages/               one route per file; thin composition only
  src/components/          reusable UI: widgets/, review/, settings/, buckets/,
                           reporters/, dashboard/, layout/, social-export/, common/, ui/
  src/services/            http.js (fetch wrapper) + api/ (per-domain modules)
  src/contexts/            AuthContext only
  src/locales/             en.json, or.json, hi.json (always update all three)
widgets/                   standalone Cloud Run Job: scrapes widget data into Postgres
  fetcher/                 entrypoint
  plugins/                 one file per widget data source
  widgets_core/            shared scraper helpers
docs/                      CONVENTIONS.md, ARCHITECTURE.md, plans/
.github/workflows/         ci.yml, deploy-uat.yml, deploy-prod.yml
```

## 3. Data flow

```
  Reporter mobile app
        |
        |  POST /stories  (Bearer JWT)
        v
  +-----------------+        +----------------+
  |  FastAPI api/   | <----> |  Postgres DB   |
  +-----------------+        +----------------+
        ^                            ^
        |  GET/PUT /stories/...      |
        |                            |
  Reviewer panel  --------------------
   (review, edit, translate, place on page)
        |
        |  POST /editions/{id}/export   (admin/editions/export.py)
        v
   IDML file  -->  download for InDesign
```

Widget data flows in parallel: `widgets/` Cloud Run Job runs on a schedule, writes
snapshots into Postgres, and the panel reads them via `/widgets` endpoints.

## 4. Auth path

```
MSG91 OTP widget (panel)
  -> POST /auth/msg91-login   (api/app/routers/auth.py)
  -> backend verifies access_token with MSG91, issues app JWT
  -> panel stores JWT, sends `Authorization: Bearer <jwt>` on every call
       (reviewer-panel/src/services/http.js)
  -> FastAPI dependency `get_current_user` (api/app/deps.py) decodes + loads user
  -> `get_org_admin` wraps `get_current_user` for admin-only routes
```

Org-scoped reads/writes go through `app.utils.scope.get_owned_or_404` — never hand-roll
`db.query(...).filter(org_id=...)`.

## 5. Deploy

GitHub Actions, push-to-deploy. No manual `gcloud` for normal releases.

- `push develop` -> `.github/workflows/deploy-uat.yml`  -> UAT (Cloud Run + Firebase Hosting)
- `push main`    -> `.github/workflows/deploy-prod.yml` -> prod
- every PR       -> `.github/workflows/ci.yml`          -> tests + build

The widget-fetcher Cloud Run Job is deployed from `widgets/cloudbuild-fetcher.yaml`.

## 6. Where to find X

- **Adding a new admin tab** — endpoint: `api/app/routers/admin/<group>.py` (register in
  `api/app/routers/admin/__init__.py`); UI tab: `reviewer-panel/src/components/settings/`
  rendered from `reviewer-panel/src/pages/SettingsPage.jsx`.
- **Adding a new widget** — renderer: `reviewer-panel/src/components/widgets/<Kind>.jsx`
  plus an entry in `reviewer-panel/src/components/widgets/index.js` (CATALOG); scraper:
  `widgets/plugins/<kind>.py`.
- **Adding a new endpoint** — pick the matching router in `api/app/routers/`; if a brand
  new resource group, add the file and register it in `api/app/routers/__init__.py`.
  Front-end caller goes in `reviewer-panel/src/services/api/<domain>.js`.
- **Changing the seed data** — `api/app/scripts/seed_dev.py`.
- **Editing translations** — `reviewer-panel/src/locales/{en,or,hi}.json` (all three).
