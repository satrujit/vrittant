-- News Feed page was added without a corresponding entitlement migration,
-- and EntitlementsModal.jsx didn't list `news_feed` in its toggle set, so
-- existing reviewers/reporters never received the grant and admins had no
-- UI to award it. The modal is fixed in this same commit; this backfill
-- handles the existing population.
--
-- Heuristic: anyone who already has `review` or `stories` is a working
-- editorial user and should see News Feed too. Skip users who already
-- have it (idempotent).
--
-- Apply to both vrittant_uat and vrittant.

INSERT INTO entitlements (user_id, page_key)
SELECT DISTINCT e.user_id, 'news_feed'
FROM entitlements e
WHERE e.page_key IN ('review', 'stories')
  AND NOT EXISTS (
    SELECT 1 FROM entitlements x
    WHERE x.user_id = e.user_id AND x.page_key = 'news_feed'
  );
