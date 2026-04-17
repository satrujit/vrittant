-- Drop the failed page-layout / IDML export module.
ALTER TABLE stories DROP COLUMN IF EXISTS layout_config;
ALTER TABLE story_revisions DROP COLUMN IF EXISTS layout_config;
DROP TABLE IF EXISTS layout_templates;
