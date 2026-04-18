-- Idempotency table for the Gupshup WhatsApp inbound webhook.
-- Gupshup retries non-2xx (and occasionally on flaky 2xx); we record every
-- processed message_id and short-circuit duplicate deliveries.
--
-- Apply to both `vrittant_uat` and `vrittant` (same Cloud SQL instance,
-- different databases) via cloud-sql-proxy on port 5433. The pipeline does
-- not run migrations.

CREATE TABLE IF NOT EXISTS whatsapp_inbound_dedup (
    message_id  VARCHAR PRIMARY KEY,
    received_at TIMESTAMP NOT NULL DEFAULT NOW()
);
