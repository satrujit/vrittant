# Deployment Pipeline & Multi-Environment Design

**Date**: 2026-04-16
**Status**: Approved

## Goal

Set up a production-grade deployment pipeline for Vrittant with:
- GitHub monorepo under `Vrittant/vrittant`
- Three environments: localhost, UAT, production
- Automated CI/CD via GitHub Actions
- Test infrastructure for both frontend and backend

## Repository Structure

```
Vrittant/vrittant (monorepo)
├── api/                          # FastAPI backend
│   ├── app/
│   │   ├── config.py             # Multi-env settings via ENV var
│   │   ├── main.py
│   │   ├── models/
│   │   ├── routers/
│   │   └── ...
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_*.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   └── pytest.ini
├── reviewer-panel/               # React + Vite frontend
│   ├── src/
│   ├── .env.local                # localhost config
│   ├── .env.uat                  # UAT config
│   ├── .env.production           # production config
│   ├── vitest.config.js
│   └── package.json
├── .github/
│   └── workflows/
│       ├── ci.yml                # Tests on every PR + push
│       ├── deploy-uat.yml        # Deploy to UAT on push to develop
│       └── deploy-prod.yml       # Deploy to prod on push to main
├── .gitignore
└── docs/
    └── plans/
```

## Environment Matrix

| Attribute        | Local              | UAT                              | Production                       |
|------------------|--------------------|----------------------------------|----------------------------------|
| API URL          | localhost:8000     | vrittant-api-uat-*.run.app       | vrittant-api-*.run.app           |
| Frontend URL     | localhost:5173     | vrittant-uat.web.app             | vrittant.in                      |
| Cloud Run svc    | -                  | vrittant-api-uat                 | vrittant-api                     |
| Database         | SQLite (local)     | Cloud SQL (vrittant-db-uat)      | Cloud SQL (vrittant-db)          |
| Firebase site    | -                  | vrittant-uat                     | vrittant-f5ef2 (default)         |
| Branch           | any                | develop                          | main                             |
| GCP Project      | -                  | vrittant-f5ef2                   | vrittant-f5ef2                   |

## CI/CD Pipeline

### Trigger Strategy (branch-based)

```
feature/* ──PR──> develop ──PR──> main
    │                │               │
    ▼                ▼               ▼
 Tests only    Tests + UAT     Tests + Prod
```

### GitHub Actions Workflows

**ci.yml** (all pushes + PRs):
- Backend: install deps, run pytest
- Frontend: install deps, run vitest, run vite build

**deploy-uat.yml** (push to develop):
- Run tests (same as ci.yml)
- Build & deploy API to Cloud Run `vrittant-api-uat`
- Build frontend with `.env.uat` & deploy to Firebase `vrittant-uat`

**deploy-prod.yml** (push to main):
- Run tests
- Build & deploy API to Cloud Run `vrittant-api`
- Build frontend with `.env.production` & deploy to Firebase default site

### GitHub Secrets Required

| Secret              | Purpose                                    |
|---------------------|--------------------------------------------|
| GCP_SA_KEY          | Service account JSON for gcloud CLI        |
| FIREBASE_TOKEN      | CI token for Firebase Hosting deploys      |
| SARVAM_API_KEY      | Sarvam AI API key (used in tests if needed)|
| DATABASE_URL_PROD   | Production Cloud SQL connection string     |
| DATABASE_URL_UAT    | UAT Cloud SQL connection string            |
| SECRET_KEY          | JWT signing secret                         |

## Test Strategy

### Backend (pytest)

- Existing: 14 test files covering revisions, templates, org admin
- Add: API smoke tests for auth, stories CRUD, news articles, search
- Add: model validation tests
- Use SQLite in-memory for test DB (already in conftest.py)

### Frontend (Vitest)

- New: API service function tests (mock fetch calls)
- New: critical component render tests (smoke tests)
- New: utility function tests

## UAT Cloud SQL Setup

Create a separate database instance or a separate database on the same instance:
- Option: same Cloud SQL instance, new database named `vrittant_uat`
- Connection via Cloud SQL Auth Proxy in Cloud Run (same as production)
- Keeps costs minimal (no second instance)

## Migration Strategy

1. Create `Vrittant` GitHub org (or use personal `satrujit` account)
2. Create `vrittant` monorepo
3. Move backend code into `api/` directory
4. Move frontend code into `reviewer-panel/` directory
5. Set up environment config files
6. Add GitHub Actions workflows
7. Add frontend test infrastructure (Vitest)
8. Push to GitHub, configure secrets
9. Create `develop` branch
10. Set up UAT Cloud Run service + Firebase site
