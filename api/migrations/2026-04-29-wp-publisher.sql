-- 2026-04-29 — auto-push approved stories to WordPress as drafts
--
-- Vrittant approves a story → sweep pushes it to the org's WordPress
-- as a `status=draft` post. WP team reviews/publishes/trashes from the
-- WP admin. Status mirrors back to Vrittant via the same sweep so
-- editors here can see whether a story went live.
--
-- All schema additions; reversible. Safe to apply with API serving.

BEGIN;

-- 1. Per-story push state
ALTER TABLE stories
  ADD COLUMN wp_post_id        INTEGER,
  ADD COLUMN wp_url             VARCHAR,
  ADD COLUMN wp_pushed_at       TIMESTAMP,
  ADD COLUMN wp_push_status     VARCHAR(40),  -- pending | ok | failed | retract | skipped_no_config | skipped_wp_status_<x>
  ADD COLUMN wp_push_error      TEXT,
  ADD COLUMN wp_push_attempts   INTEGER NOT NULL DEFAULT 0;

-- Sweep filters on (wp_push_status, attempts). Partial index keeps the
-- index tiny — the vast majority of stories never enter the WP pipeline.
CREATE INDEX ix_stories_wp_pending
  ON stories (organization_id, wp_push_status)
  WHERE wp_push_status IN ('pending', 'retract');

-- 2. Per-org WordPress configuration
--
-- Stored as JSONB on org_configs so the team can update via a simple
-- UPDATE statement once they have credentials. Shape:
--   {
--     "base_url": "https://pragativadi.com",
--     "username": "vrittant-bot",
--     "app_password_secret": "WP_PRAGATIVADI_APP_PASSWORD",
--     "default_author_id": 12,
--     "default_status": "draft",
--     "category_map": { "crime": 5, "politics": 8, "sports": 14 }
--   }
-- The app_password itself lives in Secret Manager, referenced by name.
ALTER TABLE org_configs ADD COLUMN wordpress_config JSONB;

COMMIT;
