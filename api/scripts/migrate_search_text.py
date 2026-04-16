#!/usr/bin/env python3
"""
Migration: Enable pg_trgm, add search_text column, backfill, create GIN index.

Run via cloud-sql-proxy:
    cloud-sql-proxy vrittant-f5ef2:asia-south1:vrittant-db &
    python scripts/migrate_search_text.py

Or set DATABASE_URL env var to point to your DB.
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://vrittant_user:vrittant_pass@127.0.0.1:5432/vrittant_db",
)

engine = create_engine(DATABASE_URL)

STEPS = [
    # 1. Enable pg_trgm extension
    "CREATE EXTENSION IF NOT EXISTS pg_trgm;",

    # 2. Add search_text column if it doesn't exist
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'stories' AND column_name = 'search_text'
        ) THEN
            ALTER TABLE stories ADD COLUMN search_text TEXT DEFAULT '' NOT NULL;
        END IF;
    END $$;
    """,

    # 3. Backfill search_text from headline + location + paragraphs
    #    paragraphs is JSON array of objects with "text" keys
    """
    UPDATE stories
    SET search_text = COALESCE(headline, '') || ' ' ||
                      COALESCE(location, '') || ' ' ||
                      COALESCE(
                          (SELECT string_agg(elem->>'text', ' ')
                           FROM jsonb_array_elements(paragraphs::jsonb) AS elem
                           WHERE elem->>'text' IS NOT NULL AND elem->>'text' != ''),
                          ''
                      )
    WHERE search_text = '' OR search_text IS NULL;
    """,

    # 4. Create GIN trigram index for fast similarity search
    """
    CREATE INDEX IF NOT EXISTS ix_stories_search_trgm
    ON stories USING GIN (search_text gin_trgm_ops);
    """,
]


def main():
    with engine.connect() as conn:
        for i, sql in enumerate(STEPS, 1):
            print(f"Step {i}/{len(STEPS)}...")
            conn.execute(text(sql))
            conn.commit()
            print(f"  Done.")
    print("\nMigration complete! pg_trgm enabled, search_text backfilled, GIN index created.")


if __name__ == "__main__":
    main()
