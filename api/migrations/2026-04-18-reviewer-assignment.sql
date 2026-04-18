-- Reviewer Assignment feature migration
-- Adds: user beats (categories/regions), story assignment fields, audit log table.
-- Pre-flight required: zero reporters with empty area_name (enforced below via NOT NULL).

ALTER TABLE users ADD COLUMN IF NOT EXISTS categories JSON NOT NULL DEFAULT '[]';
ALTER TABLE users ADD COLUMN IF NOT EXISTS regions JSON NOT NULL DEFAULT '[]';

ALTER TABLE stories ADD COLUMN IF NOT EXISTS assigned_to VARCHAR REFERENCES users(id);
ALTER TABLE stories ADD COLUMN IF NOT EXISTS assigned_match_reason VARCHAR;
CREATE INDEX IF NOT EXISTS ix_stories_assigned_to ON stories(assigned_to);

CREATE TABLE IF NOT EXISTS story_assignment_log (
  id VARCHAR PRIMARY KEY,
  story_id VARCHAR NOT NULL REFERENCES stories(id),
  from_user_id VARCHAR REFERENCES users(id),
  to_user_id VARCHAR NOT NULL REFERENCES users(id),
  assigned_by VARCHAR REFERENCES users(id),
  reason VARCHAR NOT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_story_assignment_log_story_id ON story_assignment_log(story_id);

-- Enforce reporter area_name (pre-flight returned zero rows)
ALTER TABLE users ALTER COLUMN area_name SET NOT NULL;
