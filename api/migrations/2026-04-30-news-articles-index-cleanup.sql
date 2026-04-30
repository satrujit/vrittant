-- 2026-04-30 — drop two redundant indexes on news_articles.
--
-- Why:
--   ix_news_articles_category   — fully covered by the composite
--                                 ix_news_articles_cat_pub which leads
--                                 with the same column. Postgres uses
--                                 the composite for any "WHERE category
--                                 = ?" query, leaving the standalone
--                                 index as pure write overhead.
--   ix_news_articles_country    — every row has country='IN' for the
--                                 Vrittant ingest, so the index has
--                                 zero discriminating power and just
--                                 costs INSERT time + bloat.
--
-- Apply on BOTH databases (vrittant_uat AND vrittant) via cloud-sql-proxy
-- on port 5433. Pipeline does NOT run migrations.
--
-- Run order: this file is independent of any code change. Safe to apply
-- before or after the matching code deploy. The retention sweep that
-- ships alongside (POST /internal/sweep-news-retention) does not depend
-- on these indexes.

DROP INDEX IF EXISTS ix_news_articles_category;
DROP INDEX IF EXISTS ix_news_articles_country;

-- While we're here: ensure the indexes the model declares actually exist.
-- ix_news_articles_source and ix_news_articles_cat_pub were declared in
-- the model but never made it into prod (the table predates those
-- entries in __table_args__, and create_all() doesn't add indexes to
-- existing tables). The news-feed source filter is now a hot path
-- (quick-source chips), so we want the source index in place.
CREATE INDEX IF NOT EXISTS ix_news_articles_source
    ON news_articles (source);
CREATE INDEX IF NOT EXISTS ix_news_articles_cat_pub
    ON news_articles (category, published_at);
