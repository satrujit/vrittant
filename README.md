# Vrittant

Editorial review panel for Odia newspapers.

## Repository Structure

```
├── api/              # FastAPI backend
├── reviewer-panel/   # React + Vite frontend
└── .github/workflows # CI/CD pipelines
```

## Environments

| Environment | API | Frontend | Branch |
|-------------|-----|----------|--------|
| Local | `localhost:8000` | `localhost:5173` | any |
| UAT | `vrittant-api-uat-*.run.app` | `vrittant-uat.web.app` | `develop` |
| Production | `vrittant-api-*.run.app` | `vrittant.in` | `main` |

## Local Development

### Backend

```bash
cd api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env  # edit with your values
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd reviewer-panel
npm install
npm run dev  # starts on localhost:5173, points to localhost:8000
```

### Running Tests

```bash
# Backend
cd api && pytest

# Frontend
cd reviewer-panel && npm test
```

## Deployment

Deployments are automated via GitHub Actions:

- **Push to `develop`** → deploys to UAT
- **Push to `main`** → deploys to Production

### Manual deployment (if needed)

```bash
# Backend
cd api
gcloud run deploy vrittant-api --source . --region asia-south1 --project vrittant-f5ef2 --allow-unauthenticated

# Frontend
cd reviewer-panel
npx vite build
npx firebase deploy --only hosting:production
```

## Git Workflow

1. Create feature branch from `develop`
2. Make changes, push, create PR to `develop`
3. CI runs tests automatically
4. Merge to `develop` → auto-deploys to UAT
5. Test on UAT, then create PR from `develop` → `main`
6. Merge to `main` → auto-deploys to Production
