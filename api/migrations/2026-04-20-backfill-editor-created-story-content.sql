-- 2026-04-20-backfill-editor-created-story-content.sql
--
-- Hotfix backfill: editor-created stories (source = 'Editor Created') were
-- created with empty Story.headline / Story.paragraphs and any subsequent
-- saves were written ONLY to story_revisions. The list endpoints read from
-- Story.headline / Story.paragraphs, so users saw their saved content as
-- "lost". The code fix in this same hotfix now writes editor-created
-- content directly to the Story row; this script repairs rows already
-- created in the broken state by copying revision content back into Story.
--
-- Safe to re-run: only updates rows where Story content is empty AND a
-- non-empty revision exists.
--
-- Apply to BOTH databases on the same instance:
--   psql ... -d vrittant_uat -f this-file.sql
--   psql ... -d vrittant     -f this-file.sql

BEGIN;

-- Show what we're about to fix.
SELECT
    s.id,
    s.created_at,
    s.headline       AS story_headline,
    r.headline       AS revision_headline,
    json_array_length(COALESCE(s.paragraphs, '[]'::json))  AS story_para_count,
    json_array_length(COALESCE(r.paragraphs, '[]'::json))  AS rev_para_count
FROM stories s
JOIN story_revisions r ON r.story_id = s.id
WHERE s.source = 'Editor Created'
  AND (s.headline IS NULL OR s.headline = '')
  AND (s.paragraphs IS NULL OR s.paragraphs::text = '[]')
  AND (COALESCE(r.headline, '') <> '' OR json_array_length(COALESCE(r.paragraphs, '[]'::json)) > 0);

-- Mirror revision content back onto the Story row.
UPDATE stories s
SET
    headline   = COALESCE(NULLIF(r.headline, ''), s.headline),
    paragraphs = CASE
                     WHEN json_array_length(COALESCE(r.paragraphs, '[]'::json)) > 0
                         THEN r.paragraphs
                     ELSE s.paragraphs
                 END,
    updated_at = GREATEST(s.updated_at, r.updated_at)
FROM story_revisions r
WHERE r.story_id = s.id
  AND s.source = 'Editor Created'
  AND (s.headline IS NULL OR s.headline = '')
  AND (s.paragraphs IS NULL OR s.paragraphs::text = '[]')
  AND (COALESCE(r.headline, '') <> '' OR json_array_length(COALESCE(r.paragraphs, '[]'::json)) > 0);

-- Refresh search_text for affected rows so search picks up the recovered headlines.
UPDATE stories s
SET search_text = TRIM(BOTH ' ' FROM
        COALESCE(s.headline, '') || ' ' ||
        COALESCE(s.location, '') || ' ' ||
        (
            SELECT COALESCE(string_agg(p->>'text', ' '), '')
            FROM json_array_elements(COALESCE(s.paragraphs, '[]'::json)) p
        )
    )
WHERE s.source = 'Editor Created'
  AND s.headline IS NOT NULL
  AND s.headline <> '';

-- Sanity check: no editor-created story should still have empty headline
-- when a revision with a headline exists.
SELECT COUNT(*) AS still_broken
FROM stories s
JOIN story_revisions r ON r.story_id = s.id
WHERE s.source = 'Editor Created'
  AND (s.headline IS NULL OR s.headline = '')
  AND r.headline IS NOT NULL
  AND r.headline <> '';

COMMIT;
