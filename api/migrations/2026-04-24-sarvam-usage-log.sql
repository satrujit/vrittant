-- Sarvam AI per-call cost ledger.
--
-- Every call we make to Sarvam (chat / translate / stt / tts) writes
-- a row here so we can answer two pricing questions:
--
--   1. What did this story cost end-to-end? (sum WHERE story_id = ?)
--   2. What is each non-story bucket costing us per month?
--      (sum WHERE bucket = ? GROUP BY date_trunc('month', created_at))
--
-- Attribution is set via a Python contextvar (see services/sarvam_client.py)
-- so request handlers don't have to plumb story_id through every call.
--
-- One row = one HTTP request to Sarvam. Cost is computed at write time
-- using the static PRICING dict in sarvam_client.py — that mirrors
-- Sarvam's published rates exactly, so the numbers should match the
-- monthly invoice. Reconcile periodically and update PRICING if rates
-- change.

CREATE TABLE IF NOT EXISTS sarvam_usage_log (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- What was called
    service         TEXT NOT NULL,        -- 'chat' | 'translate' | 'stt' | 'tts' | 'vision'
    model           TEXT NOT NULL,        -- 'sarvam-30b', 'mayura:v1', 'bulbul:v3', 'saarika:v2.5'
    endpoint        TEXT,                 -- URL path, for debugging

    -- Usage units (only the ones relevant to the service are populated)
    input_tokens    INTEGER,              -- chat
    cached_tokens   INTEGER,              -- chat (subset of input_tokens, billed cheaper)
    output_tokens   INTEGER,              -- chat
    characters      INTEGER,              -- translate, tts
    audio_seconds   INTEGER,              -- stt (rounded up per Sarvam's billing rule)
    pages           INTEGER,              -- vision

    -- Cost in INR computed from the above + PRICING table
    cost_inr        NUMERIC(10, 4) NOT NULL,

    -- Attribution
    story_id        VARCHAR REFERENCES stories(id) ON DELETE SET NULL,
    bucket          TEXT,                 -- 'news_fetcher' | 'widgets' | 'search' | 'whatsapp_intake' | NULL
    user_id         VARCHAR,              -- whoever triggered it; NULL for system jobs

    -- Diagnostics
    duration_ms     INTEGER,
    status_code     INTEGER,
    error           TEXT                  -- short error reason if the call failed
);

-- Per-story rollup (the most common analytical query)
CREATE INDEX IF NOT EXISTS idx_sarvam_usage_story
    ON sarvam_usage_log (story_id) WHERE story_id IS NOT NULL;

-- Bucket-by-month rollup for overhead tracking
CREATE INDEX IF NOT EXISTS idx_sarvam_usage_bucket_date
    ON sarvam_usage_log (bucket, created_at);

-- Time-range scans for invoicing reconciliation
CREATE INDEX IF NOT EXISTS idx_sarvam_usage_created
    ON sarvam_usage_log (created_at);

-- Catch silent attribution misses (rows with neither story_id nor bucket).
-- Surfacing these in dashboards forces us to instrument every callsite.
CREATE INDEX IF NOT EXISTS idx_sarvam_usage_unattributed
    ON sarvam_usage_log (created_at)
    WHERE story_id IS NULL AND bucket IS NULL;

COMMENT ON TABLE sarvam_usage_log IS
    'Per-call Sarvam AI cost ledger. Written by services/sarvam_client.py. Backend-only — not exposed via any API endpoint.';
