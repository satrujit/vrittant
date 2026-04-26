-- 2026-04-26 — per-org canonical edition names
--
-- Adds OrgConfig.edition_names (List[str]) backing the auto-rolling
-- 7-day edition window on the Page Arrangement screen. When the list
-- is non-empty, /admin/editions list calls (filtered by date) ensure
-- one Edition row per name exists for the requested date and the next
-- 6 days; manual editions with different titles are untouched.
--
-- Apply to BOTH databases on the shared instance:
--   vrittant_uat   (UAT)
--   vrittant       (PROD)

BEGIN;

ALTER TABLE org_configs
    ADD COLUMN IF NOT EXISTS edition_names JSON NOT NULL DEFAULT '[]'::json;

-- Seed Pragativadi with the canonical 6-edition list.
-- Idempotent: re-running overwrites with the same canonical set.
UPDATE org_configs
SET edition_names = '[
    "Bhubaneswar",
    "Central Odisha",
    "Coastal Odisha",
    "Balasore-Keonjhar",
    "Sambalpur",
    "Bhawanipatna"
]'::json
WHERE organization_id IN (
    SELECT id FROM organizations WHERE slug = 'pragativadi'
);

COMMIT;
