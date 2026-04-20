-- 2026-04-20-promote-editor-created-drafts.sql
--
-- Editor-created stories were historically created with status="draft".
-- The default admin list views filter drafts out (exclude_status=draft),
-- so editors couldn't see their own saved work. The code now creates
-- them as status="in_progress"; this one-off promotes existing drafts
-- that actually have content (headline or at least one paragraph) to
-- "in_progress" so they become visible.
--
-- Abandoned empty draft stubs (no headline, no paragraphs) are left
-- as drafts — they're not worth surfacing.
--
-- Safe to re-run; only affects editor-created drafts with content.

BEGIN;

UPDATE stories
SET status = 'in_progress',
    updated_at = GREATEST(updated_at, now() AT TIME ZONE 'Asia/Kolkata')
WHERE source = 'Editor Created'
  AND status = 'draft'
  AND (
      COALESCE(headline, '') <> ''
      OR json_array_length(COALESCE(paragraphs, '[]'::json)) > 0
  );

-- Confirm
SELECT status, COUNT(*) FROM stories
WHERE source = 'Editor Created'
GROUP BY status
ORDER BY status;

COMMIT;
