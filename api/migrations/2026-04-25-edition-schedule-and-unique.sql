-- 2026-04-25-edition-schedule-and-unique.sql
-- Adds per-org edition templates that drive the nightly auto-create
-- job, plus a uniqueness guard so the job is naturally idempotent.

ALTER TABLE org_configs
  ADD COLUMN IF NOT EXISTS edition_schedule JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Same (org, date, title) can never produce two editions. The seed
-- endpoint relies on ON CONFLICT DO NOTHING against this constraint.
CREATE UNIQUE INDEX IF NOT EXISTS uq_editions_org_date_title
  ON editions (organization_id, publication_date, title);
