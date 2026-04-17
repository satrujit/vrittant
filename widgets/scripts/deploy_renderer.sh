#!/usr/bin/env bash
# Build + deploy widget-renderer (Cloud Run Service) — single shared instance for UAT + prod.
set -euo pipefail

PROJECT="${PROJECT:-vrittant-f5ef2}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-widget-renderer}"
INSTANCE="${INSTANCE:-${PROJECT}:${REGION}:vrittant-db}"
IMAGE="${IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/cloud-run-source-deploy/${SERVICE}:latest}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL must be set." >&2
  exit 1
fi

cd "$(dirname "$0")/.."

# 1. Build via Cloud Build
gcloud builds submit \
  --project "$PROJECT" \
  --config cloudbuild-renderer.yaml \
  --substitutions "_IMAGE=$IMAGE" \
  .

# 2. Deploy to Cloud Run
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5 \
  --concurrency 80 \
  --timeout 30 \
  --add-cloudsql-instances "$INSTANCE" \
  --set-env-vars "DATABASE_URL=${DATABASE_URL},WIDGET_SCHEMA=widgets"

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --project "$PROJECT" --format='value(status.url)')
echo "Renderer deployed: $URL"
