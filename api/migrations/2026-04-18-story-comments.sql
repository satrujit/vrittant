-- Editorial comments on stories — flat thread visible to reviewers/admins.
-- Apply to BOTH vrittant_uat and vrittant DBs via cloud-sql-proxy.

CREATE TABLE IF NOT EXISTS story_comments (
    id VARCHAR PRIMARY KEY,
    story_id VARCHAR NOT NULL REFERENCES stories(id),
    author_id VARCHAR NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_story_comments_story_id_created
    ON story_comments(story_id, created_at);
