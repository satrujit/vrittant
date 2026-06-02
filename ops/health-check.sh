#!/bin/bash
# Server health monitoring — runs every 5 min via cron.
# Sends Telegram alert ONLY when something is wrong.

# Secrets injected on the server (see /opt/vrittant/health-check.sh).
# Do NOT commit real values. The live server copy has these hardcoded;
# this repo copy is the source-of-truth for the LOGIC only.
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-REDACTED}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-REDACTED}"

ERRORS=()

# 1. Prod API responding?
# Blue-green: prod runs on EITHER 8080 (blue) or 8082 (green) depending
# on which slot the last deploy promoted. Healthy if EITHER returns 200.
# (Checking a single hardcoded port produces 000 false-alarms whenever
# the active slot is the other one.)
PROD_BLUE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:8080/health)
PROD_GREEN=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:8082/health)
if [ "$PROD_BLUE" != "200" ] && [ "$PROD_GREEN" != "200" ]; then
    ERRORS+=("🔴 Prod API down (blue=$PROD_BLUE green=$PROD_GREEN)")
fi

# 2. UAT API responding?
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://localhost:8081/health)
if [ "$HTTP_CODE" != "200" ]; then
    ERRORS+=("🟡 UAT API returned $HTTP_CODE")
fi

# 3. PostgreSQL accepting connections?
if ! docker exec vrittant-db-1 pg_isready -U vrittant -q 2>/dev/null; then
    ERRORS+=("🔴 Prod PostgreSQL not ready")
fi

# 4. Disk usage > 80%?
DISK_PCT=$(df / --output=pcent | tail -1 | tr -d " %")
if [ "$DISK_PCT" -gt 80 ]; then
    ERRORS+=("🟠 Disk usage at ${DISK_PCT}%")
fi

# 5. Memory usage > 90%?
MEM_PCT=$(free | awk "/Mem:/{printf \"%.0f\", \$3/\$2 * 100}")
if [ "$MEM_PCT" -gt 90 ]; then
    ERRORS+=("🟠 Memory usage at ${MEM_PCT}%")
fi

# 6. Any container restarting?
RESTARTS=$(docker ps --format "{{.Names}} {{.Status}}" | grep -i "restarting" || true)
if [ -n "$RESTARTS" ]; then
    ERRORS+=("🔴 Container restarting: $RESTARTS")
fi

# 7. SSL cert expiring within 7 days?
EXPIRY=$(echo | openssl s_client -connect api.vrittant.in:443 -servername api.vrittant.in 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [ -n "$EXPIRY" ]; then
    EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null)
    NOW_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
    if [ "$DAYS_LEFT" -lt 7 ]; then
        ERRORS+=("🟠 SSL cert expires in ${DAYS_LEFT} days")
    fi
fi

# Report
if [ ${#ERRORS[@]} -gt 0 ]; then
    MSG="⚠️ *Vrittant Server Alert*%0A%0A"
    for e in "${ERRORS[@]}"; do
        MSG+="${e}%0A"
    done
    MSG+="%0A_$(date "+%Y-%m-%d %H:%M UTC")_"

    curl -s -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}&text=${MSG}&parse_mode=Markdown" \
        > /dev/null 2>&1

    echo "$(date -Iseconds) ALERT: ${ERRORS[*]}"
    exit 1
else
    echo "$(date -Iseconds) OK: prod_blue=${PROD_BLUE} prod_green=${PROD_GREEN} uat=200 db=ready disk=${DISK_PCT}% mem=${MEM_PCT}%"
fi
