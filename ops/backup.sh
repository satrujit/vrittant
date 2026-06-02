#!/bin/bash
set -euo pipefail

BACKUP_DIR=/opt/vrittant/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ERRORS=0

# Dump prod DB
echo "Starting prod backup..."
if docker exec vrittant-db-1 pg_dump -U vrittant -d vrittant -F c -f /tmp/backup_${TIMESTAMP}.dump; then
    docker cp vrittant-db-1:/tmp/backup_${TIMESTAMP}.dump ${BACKUP_DIR}/vrittant_${TIMESTAMP}.dump
    docker exec vrittant-db-1 rm /tmp/backup_${TIMESTAMP}.dump
    PROD_SIZE=$(du -sh ${BACKUP_DIR}/vrittant_${TIMESTAMP}.dump | cut -f1)
    echo "Prod backup OK: ${PROD_SIZE}"
else
    echo "ERROR: Prod pg_dump FAILED"
    ERRORS=$((ERRORS + 1))
fi

# Dump UAT DB
echo "Starting UAT backup..."
if docker exec vrittant-db-uat-1 pg_dump -U vrittant -d vrittant_uat -F c -f /tmp/backup_uat_${TIMESTAMP}.dump; then
    docker cp vrittant-db-uat-1:/tmp/backup_uat_${TIMESTAMP}.dump ${BACKUP_DIR}/vrittant_uat_${TIMESTAMP}.dump
    docker exec vrittant-db-uat-1 rm /tmp/backup_uat_${TIMESTAMP}.dump
    UAT_SIZE=$(du -sh ${BACKUP_DIR}/vrittant_uat_${TIMESTAMP}.dump | cut -f1)
    echo "UAT backup OK: ${UAT_SIZE}"
else
    echo "ERROR: UAT pg_dump FAILED"
    ERRORS=$((ERRORS + 1))
fi

# Only clean old backups if BOTH succeeded
if [ $ERRORS -eq 0 ]; then
    find ${BACKUP_DIR} -name "vrittant_*.dump" -mtime +7 -delete
    find ${BACKUP_DIR} -name "vrittant_uat_*.dump" -mtime +7 -delete
    echo "Old backups cleaned. All OK."
else
    echo "WARNING: $ERRORS backup(s) failed — NOT deleting old backups"
    exit 1
fi
