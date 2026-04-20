-- 2026-04-20-stories-reviewed-by-uat-catchup.sql
--
-- Schema drift catch-up: vrittant_uat is missing reviewed_by / reviewed_at
-- on the stories table. Production already has them. The Story SQLAlchemy
-- model references them via Story.reviewer relationship, so any insert
-- (e.g. POST /admin/stories/create-blank) attempted on UAT raises
-- "column 'reviewed_by' of relation 'stories' does not exist".
--
-- Idempotent. Apply to vrittant_uat (and harmlessly re-applicable on prod).

ALTER TABLE stories ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR REFERENCES users(id);
ALTER TABLE stories ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITHOUT TIME ZONE;
