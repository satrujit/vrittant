-- 2026-04-26 — track attachment counts on email_intake_log
--
-- The first user-visible test of the inbound email pipeline arrived
-- without its attachment, but we had no audit data to tell whether
-- SendGrid sent attachments at all (and we silently rejected them on
-- the type allowlist) or whether Gmail's auto-forward stripped them
-- before SendGrid ever saw them.
--
-- Add three counts so the next test gives a definitive answer:
--   attachment_count_received — what SendGrid said it sent us
--   attachment_count_accepted — how many we actually attached to the Story
--   attachment_keys           — the form field names SendGrid used,
--                                so we catch any naming mismatch
--                                (e.g. attachment-1 vs attachment1)
--
-- Apply to BOTH databases:
--   vrittant_uat
--   vrittant

BEGIN;

ALTER TABLE email_intake_log
    ADD COLUMN IF NOT EXISTS attachment_count_received INTEGER,
    ADD COLUMN IF NOT EXISTS attachment_count_accepted INTEGER,
    ADD COLUMN IF NOT EXISTS attachment_keys VARCHAR;

COMMIT;
