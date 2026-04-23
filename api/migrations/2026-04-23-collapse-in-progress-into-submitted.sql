-- Collapse the editor-side draft status (`in_progress`) into the unified
-- `submitted` status used for everything that's gone through the review
-- queue at least once. This is a one-way migration — the panel's
-- create-blank endpoint now defaults to `submitted` directly, so no new
-- `in_progress` rows will be written after the API rolls forward.
--
-- Apply on BOTH databases (vrittant_uat AND vrittant) on the same
-- Cloud SQL instance via the cloud-sql-proxy:
--
--   gcloud sql connect ... --database=vrittant_uat < this.sql
--   gcloud sql connect ... --database=vrittant     < this.sql
--
-- Run BEFORE deploying the API change so the panel never sees an
-- `in_progress` story it can no longer transition.

BEGIN;

-- 1. Backfill submitted_at for any in_progress story that never got one,
--    so dashboards/leaderboards (which key off submitted_at) include them.
UPDATE stories
SET submitted_at = COALESCE(submitted_at, created_at)
WHERE status = 'in_progress';

-- 2. Flip the status itself.
UPDATE stories
SET status = 'submitted'
WHERE status = 'in_progress';

COMMIT;

-- Sanity check: should return 0
-- SELECT COUNT(*) FROM stories WHERE status = 'in_progress';
