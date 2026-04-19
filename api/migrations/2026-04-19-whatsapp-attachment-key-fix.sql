-- Backfill: WhatsApp ingestion was writing media under the key `media_url`
-- and adding a `[Attachment: ...]` text placeholder, which the reviewer
-- panel doesn't understand (it reads `media_path`). Rewrite affected
-- paragraphs so the existing stories render images in the Attachments rail
-- instead of as inline text noise.
--
-- For each paragraph object that has `media_url` but no `media_path`:
--   • copy media_url → media_path
--   • drop media_url
--   • blank out text if it starts with `[Attachment:`
--   • add `media_type: "photo"` (UAT/prod history is image-only so far)
--
-- Apply to both vrittant_uat and vrittant.

UPDATE stories
SET paragraphs = (
    SELECT jsonb_agg(
        CASE
            WHEN p ? 'media_url' AND NOT (p ? 'media_path') THEN
                (p - 'media_url')
                || jsonb_build_object(
                    'media_path', p->'media_url',
                    'media_type', 'photo',
                    'text', CASE
                        WHEN (p->>'text') LIKE '[Attachment:%' THEN ''
                        ELSE COALESCE(p->>'text', '')
                    END
                )
            ELSE p
        END
    )
    FROM jsonb_array_elements(paragraphs::jsonb) AS p
)
WHERE paragraphs::jsonb @? '$[*] ? (exists(@.media_url))';
