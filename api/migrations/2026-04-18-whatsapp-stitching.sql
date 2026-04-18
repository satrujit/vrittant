-- WhatsApp multi-message stitching: track open session window and
-- LLM-flagged unclear submissions for reviewer triage.
--
-- Apply to both `vrittant_uat` and `vrittant` (same Cloud SQL instance,
-- different databases) via cloud-sql-proxy on port 5433. The pipeline does
-- not run migrations.
ALTER TABLE stories
    ADD COLUMN IF NOT EXISTS whatsapp_session_open_until TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS needs_triage BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS ix_stories_whatsapp_open
    ON stories (reporter_id, whatsapp_session_open_until)
    WHERE whatsapp_session_open_until IS NOT NULL;
