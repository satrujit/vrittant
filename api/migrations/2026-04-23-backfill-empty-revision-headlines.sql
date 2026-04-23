-- Backfill empty story_revisions.headline from the parent story.headline.
--
-- The detail/review endpoint loads `story.revision`; the panel's
-- useReviewState prefers revision.headline when a revision row exists.
-- A blank revision.headline used to mask the (now-backfilled) parent
-- story.headline in the editor view, even though the list view rendered
-- correctly. This fills those gaps.
--
-- The frontend has also been hardened to prefer story.headline when
-- revision.headline is blank, so this migration is the data half of a
-- two-sided fix.
--
-- Apply to BOTH databases on the shared instance:
--   \c vrittant_uat   \i 2026-04-23-backfill-empty-revision-headlines.sql
--   \c vrittant       \i 2026-04-23-backfill-empty-revision-headlines.sql

UPDATE story_revisions r
SET headline = s.headline,
    updated_at = now()
FROM stories s
WHERE r.story_id = s.id
  AND s.deleted_at IS NULL
  AND (r.headline IS NULL OR trim(r.headline) = '')
  AND s.headline IS NOT NULL
  AND trim(s.headline) <> '';
