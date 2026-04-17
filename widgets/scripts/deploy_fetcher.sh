#!/usr/bin/env bash
# Build + deploy widget-fetcher (Cloud Run Job) and ensure Cloud Scheduler trigger exists.
set -euo pipefail

PROJECT="${PROJECT:-vrittant-f5ef2}"
PROJECT_NUMBER="${PROJECT_NUMBER:-829303072442}"
REGION="${REGION:-asia-south1}"
JOB="${JOB:-widget-fetcher}"
INSTANCE="${INSTANCE:-${PROJECT}:${REGION}:vrittant-db}"
IMAGE="${IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/cloud-run-source-deploy/${JOB}:latest}"
SARVAM_SECRET="${SARVAM_SECRET:-SARVAM_API_KEY}"
SCHEDULER_SA="${SCHEDULER_SA:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL must be set." >&2
  exit 1
fi

cd "$(dirname "$0")/.."

# 1. Build
gcloud builds submit \
  --project "$PROJECT" \
  --config cloudbuild-fetcher.yaml \
  --substitutions "_IMAGE=$IMAGE" \
  .

# 2. Deploy (create or update) the Cloud Run Job
if gcloud run jobs describe "$JOB" --region "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  CMD="update"
else
  CMD="create"
fi

gcloud run jobs "$CMD" "$JOB" \
  --image "$IMAGE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --memory 512Mi \
  --cpu 1 \
  --task-timeout 600 \
  --max-retries 1 \
  --set-cloudsql-instances "$INSTANCE" \
  --set-env-vars "DATABASE_URL=${DATABASE_URL},WIDGET_SCHEMA=widgets" \
  --set-secrets "SARVAM_API_KEY=${SARVAM_SECRET}:latest"

# 3. Cloud Scheduler — 00:30 IST daily
SCHED_NAME="${JOB}-daily"
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB}:run"

if gcloud scheduler jobs describe "$SCHED_NAME" --location "$REGION" --project "$PROJECT" >/dev/null 2>&1; then
  SCMD="update"
else
  SCMD="create"
fi

gcloud scheduler jobs "$SCMD" http "$SCHED_NAME" \
  --location "$REGION" \
  --project "$PROJECT" \
  --schedule "30 0 * * *" \
  --time-zone "Asia/Kolkata" \
  --uri "$JOB_URI" \
  --http-method POST \
  --oauth-service-account-email "$SCHEDULER_SA"

echo "Fetcher job + scheduler ready."
