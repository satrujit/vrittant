-- 2026-04-25-categories-revamp.sql
-- Revamp default category list across all orgs.
-- New active set: Politics, Crime, Accident, Governance, Entertainment,
-- Science, Sports, General. Older keys (business/education/health/etc.)
-- remain valid in i18n + colour map so historical stories still render,
-- but are no longer offered in the picker.
--
-- Idempotent: setting the same JSON twice is a no-op.

UPDATE org_configs
SET categories = '[
  {"key":"politics",      "label":"Politics",      "label_local":"ରାଜନୀତି",   "is_active":true},
  {"key":"crime",         "label":"Crime",         "label_local":"ଅପରାଧ",     "is_active":true},
  {"key":"accident",      "label":"Accident",      "label_local":"ଦୁର୍ଘଟଣା",   "is_active":true},
  {"key":"governance",    "label":"Governance",    "label_local":"ଶାସନ",      "is_active":true},
  {"key":"entertainment", "label":"Entertainment", "label_local":"ମନୋରଞ୍ଜନ", "is_active":true},
  {"key":"science",       "label":"Science",       "label_local":"ବିଜ୍ଞାନ",     "is_active":true},
  {"key":"sports",        "label":"Sports",        "label_local":"କ୍ରୀଡ଼ା",     "is_active":true},
  {"key":"general",       "label":"General",       "label_local":"ସାଧାରଣ",   "is_active":true}
]'::jsonb;
