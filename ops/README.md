# Ops scripts

Source-of-truth for the operational shell scripts that live on the Hetzner
prod server at `/opt/vrittant/`. These are **not** deployed automatically —
the server copies are edited in place. Keep this folder in sync by hand when
you change them on the server (and vice versa).

| Script | Runs | Purpose |
|---|---|---|
| `deploy-api.sh` | GitHub Actions (prod) | Zero-downtime blue-green deploy. Reads `.active-slot`, builds the idle slot (blue=:8080 / green=:8082), health-checks, drains the old one. |
| `health-check.sh` | cron every 5 min | Pings prod (both blue+green ports), UAT, Postgres, disk, mem, container restarts, SSL expiry. Telegram alert only on failure. |
| `backup.sh` | cron daily 03:00 | `pg_dump` of prod + UAT DBs to `/opt/vrittant/backups`, 7-day retention. |

## Secrets

`health-check.sh` references `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`. The
live server copy has these hardcoded; the repo copy is redacted. Never commit
real values.

## Blue-green note

Prod runs on **either** port 8080 (blue) or 8082 (green) depending on which
slot the last deploy promoted (tracked in `/opt/vrittant/.active-slot`).
`health-check.sh` checks BOTH ports and passes if either is healthy — a
single hardcoded port produces `000` false-alarms whenever the active slot is
the other one. (This was the cause of a ~1700-message Telegram alert storm
in June 2026.)
