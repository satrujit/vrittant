-- 2026-04-26 — re-paginate canonical editions to Page 1..Page 20
--
-- The first auto-seed pass borrowed the org's page_suggestions preset
-- to fill in pages, which gave UAT canonical editions 10 pages with
-- mixed names ("Front Page", "Page 2", "Sports", …) and prod canonical
-- editions just 2 pages ("Front", "Entertainment"). Canonical
-- geographic editions should all share the same uniform 20-page
-- layout, so wipe and recreate as Page 1 … Page 20.
--
-- SAFE because we only touch canonical editions whose pages have NO
-- story assignments yet — i.e. nothing has been laid out into them.
-- Any edition where a reviewer has already started arranging stories
-- is left untouched.
--
-- Apply to BOTH databases:
--   vrittant_uat   (UAT)
--   vrittant       (PROD)

BEGIN;

WITH safe_canonical AS (
    SELECT e.id
    FROM editions e
    WHERE e.organization_id = (SELECT id FROM organizations WHERE slug = 'pragativadi')
      AND e.title IN (
          'Bhubaneswar', 'Central Odisha', 'Coastal Odisha',
          'Balasore-Keonjhar', 'Sambalpur', 'Bhawanipatna'
      )
      AND NOT EXISTS (
          SELECT 1
          FROM edition_pages p
          JOIN edition_page_stories eps ON eps.edition_page_id = p.id
          WHERE p.edition_id = e.id
      )
)
DELETE FROM edition_pages
WHERE edition_id IN (SELECT id FROM safe_canonical);

INSERT INTO edition_pages (id, edition_id, page_number, page_name, sort_order)
SELECT
    gen_random_uuid()::text,
    e.id,
    n,
    'Page ' || n,
    n
FROM editions e
CROSS JOIN generate_series(1, 20) AS n
WHERE e.organization_id = (SELECT id FROM organizations WHERE slug = 'pragativadi')
  AND e.title IN (
      'Bhubaneswar', 'Central Odisha', 'Coastal Odisha',
      'Balasore-Keonjhar', 'Sambalpur', 'Bhawanipatna'
  )
  AND NOT EXISTS (
      SELECT 1 FROM edition_pages p WHERE p.edition_id = e.id
  );

-- Verification: every canonical Pragativadi edition without story
-- assignments should now have exactly 20 pages.
SELECT e.publication_date, e.title, COUNT(p.id) AS page_count
FROM editions e
LEFT JOIN edition_pages p ON p.edition_id = e.id
WHERE e.organization_id = (SELECT id FROM organizations WHERE slug = 'pragativadi')
  AND e.title IN (
      'Bhubaneswar', 'Central Odisha', 'Coastal Odisha',
      'Balasore-Keonjhar', 'Sambalpur', 'Bhawanipatna'
  )
GROUP BY e.publication_date, e.title
ORDER BY e.publication_date, e.title;

COMMIT;
