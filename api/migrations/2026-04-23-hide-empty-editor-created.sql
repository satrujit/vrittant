-- Hide existing editor-created stories that never got real content.
-- Before this change, clicking "+" in the panel inserted with
-- status='submitted', so empty stories pollute All Stories. Demote them
-- to 'draft' so they're filtered out everywhere; the row is still there
-- if anyone reopens the URL.
--
-- Apply to BOTH databases on the shared instance:
--   psql "host=127.0.0.1 port=5433 user=vrittant dbname=vrittant_uat" -f <this>
--   psql "host=127.0.0.1 port=5433 user=vrittant dbname=vrittant"     -f <this>

UPDATE stories
SET status = 'draft', updated_at = NOW()
WHERE source = 'Editor Created'
  AND status = 'submitted'
  AND coalesce(trim(headline), '') = ''
  AND NOT EXISTS (
    SELECT 1
    FROM json_array_elements(stories.paragraphs::json) AS p
    WHERE coalesce(trim(p->>'text'), '') <> ''
       OR (p->>'media_path') IS NOT NULL
       OR (p->>'photo_path') IS NOT NULL
  );
