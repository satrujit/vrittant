#!/usr/bin/env bash
# Run the fetcher locally against real Firestore (uses ADC credentials).
# Requires: gcloud auth application-default login
set -euo pipefail
cd "$(dirname "$0")/.."
export GCP_PROJECT="${GCP_PROJECT:-vrittant-f5ef2}"
python -m fetcher.main
