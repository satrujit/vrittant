#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export GCP_PROJECT="${GCP_PROJECT:-vrittant-f5ef2}"
exec uvicorn renderer.main:app --reload --port 8081
