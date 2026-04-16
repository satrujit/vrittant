-- Add soft delete column to stories and users
ALTER TABLE stories ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS ix_stories_deleted_at ON stories (deleted_at);

ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
CREATE INDEX IF NOT EXISTS ix_users_deleted_at ON users (deleted_at);
