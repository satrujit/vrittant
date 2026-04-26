-- 2026-04-26 — Inbound email → Story pipeline
--
-- Two changes:
--   1. Add email_forwarders + whitelisted_contributors JSON columns
--      to org_configs. Together they decide who can submit stories
--      via the SendGrid Inbound Parse webhook.
--   2. Create email_intake_log: one row per inbound email (accepted
--      OR dropped) for dedup + forensics.
--
-- Apply to BOTH databases on the shared instance:
--   vrittant_uat   (UAT)
--   vrittant       (PROD)

BEGIN;

-- ── OrgConfig allowlists ────────────────────────────────────────────────
ALTER TABLE org_configs
    ADD COLUMN IF NOT EXISTS email_forwarders JSON NOT NULL DEFAULT '[]'::json;

ALTER TABLE org_configs
    ADD COLUMN IF NOT EXISTS whitelisted_contributors JSON NOT NULL DEFAULT '[]'::json;

-- ── Intake audit log ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_intake_log (
    id              VARCHAR PRIMARY KEY,
    organization_id VARCHAR REFERENCES organizations(id),
    message_id      VARCHAR,
    from_addr       VARCHAR,
    to_addr         VARCHAR,
    forwarder_addr  VARCHAR,
    subject         VARCHAR,
    spam_score      VARCHAR,
    status          VARCHAR NOT NULL,
    story_id        VARCHAR REFERENCES stories(id),
    error_msg       TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'Asia/Kolkata')
);

CREATE INDEX IF NOT EXISTS ix_email_intake_log_organization_id
    ON email_intake_log (organization_id);

CREATE INDEX IF NOT EXISTS ix_email_intake_log_message_id
    ON email_intake_log (message_id);

CREATE INDEX IF NOT EXISTS ix_email_intake_log_story_id
    ON email_intake_log (story_id);

-- Composite index used by the dedupe lookup. We always query by
-- (organization_id, message_id) together; the single-column indexes
-- above support filter-by-org and filter-by-msgid scans separately.
CREATE INDEX IF NOT EXISTS ix_email_intake_org_msgid
    ON email_intake_log (organization_id, message_id);

COMMIT;
