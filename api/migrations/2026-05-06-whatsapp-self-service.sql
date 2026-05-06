-- 2026-05-06-whatsapp-self-service.sql
-- Adds the four tables + columns the WhatsApp self-service feature needs.
-- All ID columns are VARCHAR to match the existing convention in this codebase
-- (stories.id, users.id, organizations.id are all VARCHAR storing UUIDs as text).

BEGIN;

-- 1. Universal media buffer
CREATE TABLE IF NOT EXISTS whatsapp_pending_media (
    id                       VARCHAR PRIMARY KEY,
    sender_phone             VARCHAR NOT NULL,
    media_type               VARCHAR NOT NULL,
    gupshup_media_url        TEXT NOT NULL,
    storage_url              TEXT,
    content_hash             VARCHAR,
    caption                  TEXT,
    received_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    drained_at               TIMESTAMPTZ,
    drained_into_story_id    VARCHAR REFERENCES stories(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_pending_media_sender_received
    ON whatsapp_pending_media (sender_phone, received_at);
CREATE INDEX IF NOT EXISTS ix_pending_media_undrained
    ON whatsapp_pending_media (sender_phone)
    WHERE drained_at IS NULL;

-- 2. Confirmation msg ID on stories (for reply-quote -> add-to-story)
ALTER TABLE stories
    ADD COLUMN IF NOT EXISTS whatsapp_confirm_message_id VARCHAR;
CREATE INDEX IF NOT EXISTS ix_stories_whatsapp_confirm
    ON stories (whatsapp_confirm_message_id)
    WHERE whatsapp_confirm_message_id IS NOT NULL;

-- 3. Active per-sender thread state
CREATE TABLE IF NOT EXISTS whatsapp_thread_state (
    sender_phone           VARCHAR PRIMARY KEY,
    thread_kind            VARCHAR NOT NULL DEFAULT 'new',
    target_story_id        VARCHAR REFERENCES stories(id) ON DELETE SET NULL,
    thread_started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pending_text_count     INT NOT NULL DEFAULT 0,
    pending_media_count    INT NOT NULL DEFAULT 0,
    pending_text_concat    TEXT NOT NULL DEFAULT '',
    interactive_msg_id     VARCHAR,
    audio_warning_shown    BOOLEAN NOT NULL DEFAULT FALSE
);

-- 4. Content-level dedup
CREATE TABLE IF NOT EXISTS whatsapp_content_dedup (
    sender_phone   VARCHAR NOT NULL,
    content_hash   VARCHAR NOT NULL,
    received_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (sender_phone, content_hash)
);
CREATE INDEX IF NOT EXISTS ix_content_dedup_received
    ON whatsapp_content_dedup (received_at);

-- 5. Org default language
ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS default_language VARCHAR(2) NOT NULL DEFAULT 'or';
COMMENT ON COLUMN organizations.default_language IS
    'ISO 639-1: or=Odia (default), hi=Hindi, en=English. Drives WhatsApp reply locale.';

COMMIT;
