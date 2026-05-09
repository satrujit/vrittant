-- 2026-05-09-monthly-transcription-limit.sql
-- Per-reporter monthly STT quota.
--
-- Why: Gemini STT is cost-bounded per minute, but a single reporter
-- accidentally leaving the mic on for hours can blow the project's
-- monthly budget on their own. Enforce a 3-hour-per-month default,
-- configurable per user via direct DB edit (intentionally not in
-- the admin UI — admins should not be casually tweaking this).
--
-- Apply to BOTH vrittant_uat and vrittant DBs (same instance) via
-- cloud-sql-proxy on port 5433. Pipeline does not run migrations.

BEGIN;

-- 1. Per-user monthly cap, in HOURS. Default 3. Editable via raw SQL.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS monthly_transcription_limit INTEGER NOT NULL DEFAULT 3;

-- 2. Usage counter — seconds consumed in the current month and the
--    YYYY-MM string identifying which month that counter belongs to.
--    On first usage of a new month we reset the counter atomically
--    (see app/services/transcription_quota.add_usage). Storing the
--    month string avoids a second cron job to clear counters at
--    midnight on the 1st.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS transcription_seconds_used BIGINT NOT NULL DEFAULT 0;
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS transcription_usage_month VARCHAR(7);  -- e.g., '2026-05'

COMMIT;
