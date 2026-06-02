#!/bin/bash
set -euo pipefail
# Zero-downtime blue-green deploy for Vrittant API.
# Called by GitHub Actions after rsync of new code.
#
# How it works:
#   1. Read which slot is active (blue on :8080 or green on :8082)
#   2. Build the OTHER slot with new code
#   3. Start it and health-check
#   4. Both slots run — Nginx routes to both (zero gap)
#   5. Gracefully stop the old slot (30s drain)
#   6. Save new active slot

cd /opt/vrittant

SLOT_FILE="/opt/vrittant/.active-slot"
ACTIVE=$(cat "$SLOT_FILE" 2>/dev/null || echo "blue")

if [ "$ACTIVE" = "blue" ]; then
    NEW="green"; NEW_PORT=8082; OLD="blue"; OLD_PORT=8080
else
    NEW="blue";  NEW_PORT=8080; OLD="green"; OLD_PORT=8082
fi

echo "Current: api-${ACTIVE} on :${OLD_PORT}"
echo "Deploying: api-${NEW} on :${NEW_PORT}"

# 1. Build new slot (old container still serving traffic)
echo "Building api-${NEW}..."
docker compose build "api-${NEW}"

# 2. Start new slot
echo "Starting api-${NEW}..."
docker compose up -d "api-${NEW}"

# 3. Wait for health check (up to 30s)
echo "Waiting for api-${NEW} to be healthy..."
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${NEW_PORT}/health" > /dev/null 2>&1; then
        echo "api-${NEW} is healthy after ${i}s"
        break
    fi
    if [ "$i" = "30" ]; then
        echo "ERROR: api-${NEW} failed health check after 30s"
        echo "Rolling back — stopping api-${NEW}, keeping api-${OLD}"
        docker compose stop "api-${NEW}" 2>/dev/null
        docker compose logs "api-${NEW}" --tail 20
        exit 1
    fi
    sleep 1
done

# 4. Both are running — Nginx is routing to both. Zero downtime achieved.
echo "Both slots running. Draining old slot..."

# 5. Gracefully stop old slot (30s for in-flight requests to finish)
docker compose stop -t 30 "api-${OLD}"

# 6. Record new active slot
echo "${NEW}" > "$SLOT_FILE"
echo "Deploy complete: api-${NEW} on :${NEW_PORT} is now active"

# Cleanup
docker image prune -f > /dev/null 2>&1
docker compose ps
