-- Add prompt_sent_at to whatsapp_thread_state for cron-based debounce.
-- The background prompt_sender_loop uses this to avoid re-sending the
-- [Submit][Cancel] prompt every poll cycle.
ALTER TABLE whatsapp_thread_state
ADD COLUMN IF NOT EXISTS prompt_sent_at TIMESTAMPTZ;
