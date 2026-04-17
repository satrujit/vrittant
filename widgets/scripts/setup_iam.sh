#!/usr/bin/env bash
# One-time IAM setup for widgets.
#
# Reuses the project's default compute service account
# (${PROJECT_NUMBER}-compute@developer.gserviceaccount.com) for both the
# Cloud Run Service and the Cloud Run Job. We just need to make sure it has:
#   - roles/cloudsql.client          (to connect to vrittant-db)
#   - roles/secretmanager.secretAccessor   (to read SARVAM_API_KEY)
#   - roles/run.invoker              (so Cloud Scheduler can trigger the Job)
set -euo pipefail

PROJECT="${PROJECT:-vrittant-f5ef2}"
PROJECT_NUMBER="${PROJECT_NUMBER:-829303072442}"
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for role in roles/cloudsql.client roles/secretmanager.secretAccessor roles/run.invoker; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member "serviceAccount:${SA}" \
    --role "$role" \
    --condition=None \
    --quiet
done

echo "IAM ready for $SA"
