-- Per-phone OTP send log for rate-limiting /auth/request-otp and
-- /auth/resend-otp. One row per send attempt; queried over the last hour
-- to enforce the 1-per-60s and 5-per-hour caps. See app/models/otp_send_log.py
-- for the rationale (short version: in-memory counters don't survive Cloud
-- Run autoscaling).
--
-- Apply to BOTH vrittant_uat and vrittant on the same Cloud SQL instance.

CREATE TABLE IF NOT EXISTS otp_send_log (
    id BIGSERIAL PRIMARY KEY,
    phone TEXT NOT NULL,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite index covers the hot path (`WHERE phone = ? AND sent_at >= ?`).
CREATE INDEX IF NOT EXISTS ix_otp_send_log_phone_sent_at
    ON otp_send_log (phone, sent_at);

-- Single-column index left in place for ad-hoc admin lookups.
CREATE INDEX IF NOT EXISTS ix_otp_send_log_phone
    ON otp_send_log (phone);
