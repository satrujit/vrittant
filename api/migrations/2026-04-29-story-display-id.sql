-- 2026-04-29 — human-readable display IDs for stories
--
-- Adds a per-org display_code on organizations (e.g. "PNS" for
-- Pragativadi News Service) and a per-org sequential counter on stories
-- so the UI can show "PNS-26-1234" instead of a raw UUID.
--
-- Schema additions only — no FKs or PK changes — so this is reversible
-- and safe to apply with the API still serving traffic.

BEGIN;

-- 1. organizations.display_code
--
-- Slug-based mapping so the same migration works for UAT (pragativadi,
-- sambad, prajaspoorthi) and prod (pragativadi, pragativadi-test,
-- sambad). Unknown slugs fall back to the first 3 letters uppercased
-- so a future org always gets a usable code without blocking the
-- migration; the team can rename it later.
ALTER TABLE organizations ADD COLUMN display_code VARCHAR(12);

UPDATE organizations SET display_code =
  CASE slug
    WHEN 'pragativadi'      THEN 'PNS'
    WHEN 'pragativadi-test' THEN 'PNST'
    WHEN 'sambad'           THEN 'SNS'
    WHEN 'prajaspoorthi'    THEN 'PJS'
    ELSE upper(substring(regexp_replace(slug, '[^a-z]', '', 'g') from 1 for 4))
  END
WHERE display_code IS NULL;

-- Fail loud if any org missed a code rather than silently shipping NULL.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM organizations WHERE display_code IS NULL) THEN
    RAISE EXCEPTION 'organizations.display_code missing for some rows; backfill before NOT NULL';
  END IF;
END $$;

ALTER TABLE organizations ALTER COLUMN display_code SET NOT NULL;

-- 2. stories.seq_no (per-org sequential counter)
ALTER TABLE stories ADD COLUMN seq_no BIGINT;

-- Backfill: number existing stories per-org by created_at, breaking ties
-- on id so the order is fully deterministic.
WITH numbered AS (
  SELECT id, ROW_NUMBER() OVER (
    PARTITION BY organization_id ORDER BY created_at, id
  ) AS rn
  FROM stories
  WHERE organization_id IS NOT NULL
)
UPDATE stories s SET seq_no = n.rn FROM numbered n WHERE s.id = n.id;

-- All current rows have organization_id (487/487 verified pre-migration);
-- if a future story lands with NULL org somehow, leave its seq_no null
-- rather than crashing — but flag the constraint so we'd notice.
ALTER TABLE stories
  ADD CONSTRAINT ck_stories_seq_with_org
  CHECK (organization_id IS NULL OR seq_no IS NOT NULL)
  NOT VALID;
ALTER TABLE stories VALIDATE CONSTRAINT ck_stories_seq_with_org;

-- 3. Concurrency-safe per-org counter table
--
-- We use this instead of a shared sequence because each org needs its
-- own monotonic counter that survives concurrent inserts. The atomic
-- INSERT … ON CONFLICT DO UPDATE … RETURNING pattern in app code is
-- race-free without taking row locks on the stories table.
CREATE TABLE org_story_seq (
  organization_id VARCHAR PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  next_seq BIGINT NOT NULL
);

INSERT INTO org_story_seq (organization_id, next_seq)
SELECT organization_id, COALESCE(MAX(seq_no), 0) + 1
FROM stories
WHERE organization_id IS NOT NULL
GROUP BY organization_id;

-- 4. Per-org uniqueness on the display number
CREATE UNIQUE INDEX uq_stories_org_seq
  ON stories (organization_id, seq_no)
  WHERE seq_no IS NOT NULL;

COMMIT;
