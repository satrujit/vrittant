-- Backfill empty/null story headlines from the first line of body text.
--
-- Stories with NULL or whitespace-only headlines render as blank rows in
-- the list view. Going forward `admin_update_story` resolves the headline
-- via _derive_headline_from_paragraphs; this migration applies the same
-- rule retroactively.
--
-- Strategy:
--   1. For each affected story, scan `paragraphs` (jsonb array of
--      {id, text}) and pick the first element whose text trims to non-empty.
--   2. Take the first line of that text, trim, truncate to 120 chars
--      (with ellipsis if truncated).
--   3. Leave rows where no body paragraph has text — they need manual
--      attention (typically image-only WA forwards) and a placeholder
--      would be worse than the obvious blank.
--
-- Apply to BOTH databases on the shared instance:
--   gcloud sql connect via cloud-sql-proxy on port 5433, then
--   \c vrittant_uat   \i 2026-04-23-backfill-empty-headlines.sql
--   \c vrittant       \i 2026-04-23-backfill-empty-headlines.sql

WITH candidates AS (
    SELECT
        s.id,
        -- First non-empty paragraph text from the jsonb array.
        (
            SELECT trim(both ' \t\r' FROM split_part(elem->>'text', E'\n', 1))
            FROM json_array_elements(s.paragraphs) AS elem
            WHERE coalesce(trim(elem->>'text'), '') <> ''
            LIMIT 1
        ) AS first_line
    FROM stories s
    WHERE s.deleted_at IS NULL
      AND (s.headline IS NULL OR trim(s.headline) = '')
),
derived AS (
    SELECT
        id,
        CASE
            WHEN char_length(first_line) > 120
                THEN trim(both ' \t\r' FROM substr(first_line, 1, 119)) || '…'
            ELSE first_line
        END AS new_headline
    FROM candidates
    WHERE first_line IS NOT NULL AND first_line <> ''
)
UPDATE stories
SET headline = derived.new_headline,
    updated_at = now()
FROM derived
WHERE stories.id = derived.id;

-- Sanity: how many empty headlines remain (should be image-only forwards)
-- SELECT count(*) FROM stories
-- WHERE deleted_at IS NULL AND (headline IS NULL OR trim(headline) = '');
