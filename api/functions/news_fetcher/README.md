# News Fetcher — Cloud Function

Serverless cron job that fetches news from the **Mediastack API** every 15 minutes and stores article metadata in Cloud SQL PostgreSQL.

## Architecture

```
Cloud Scheduler (*/15 * * * *) → OIDC auth → Cloud Function (Gen2) → Mediastack API → Cloud SQL
```

## GCP Resources

| Resource | Name | Region |
|----------|------|--------|
| Cloud Function (Gen2) | `news-fetcher` | asia-south1 |
| Cloud Scheduler | `news-fetcher-cron` | asia-south1 |
| Cloud SQL Instance | `vrittant-db` | asia-south1 |
| Database | `vrittant` | — |
| Table | `news_articles` | — |
| GCP Project | `vrittant-f5ef2` | — |
| Function URL | `https://asia-south1-vrittant-f5ef2.cloudfunctions.net/news-fetcher` |
| Service Account | `829303072442-compute@developer.gserviceaccount.com` |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MEDIASTACK_KEY` | Mediastack API access key |
| `INSTANCE_CONNECTION_NAME` | Cloud SQL instance (`vrittant-f5ef2:asia-south1:vrittant-db`) |
| `DB_USER` | PostgreSQL user (default: `postgres`) |
| `DB_PASS` | PostgreSQL password |
| `DB_NAME` | Database name (default: `vrittant`) |

## Mediastack API

**Endpoint:** `http://api.mediastack.com/v1/news`

**Current fetch config:**
- `languages=en` (English)
- `countries=in` (India)
- `sort=published_desc` (newest first)
- `limit=100` (max per request)

**Available filters** (can be added to params in `main.py`):

| Parameter | Values | Example |
|-----------|--------|---------|
| `categories` | general, business, entertainment, health, science, sports, technology | `&categories=business,sports` |
| `countries` | 50+ 2-letter codes | `&countries=in,us,gb` |
| `languages` | ar, de, en, es, fr, he, it, nl, no, pt, ru, se, zh | `&languages=en,hi` |
| `keywords` | Free-text, prefix `-` to exclude | `&keywords=cricket -ipl` |
| `sources` | Source IDs, prefix `-` to exclude | `&sources=cnn,-bbc` |
| `sort` | `published_desc` (default), `published_asc`, `popularity` | `&sort=popularity` |
| `date` | YYYY-MM-DD or range (Standard plan+) | `&date=2025-01-01,2025-01-31` |
| `limit` | 1–100 (default 25) | `&limit=100` |
| `offset` | Pagination offset | `&offset=100` |

**Free plan limitation:** 30-minute delay on live news. No historical access.

## Database Schema

```sql
CREATE TABLE news_articles (
    id          VARCHAR PRIMARY KEY,
    title       VARCHAR NOT NULL,
    description TEXT,
    url         VARCHAR NOT NULL UNIQUE,   -- dedup key
    source      VARCHAR,
    author      VARCHAR,
    image_url   VARCHAR,
    category    VARCHAR,
    language    VARCHAR(5),
    country     VARCHAR(5),
    published_at TIMESTAMPTZ,
    fetched_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
ix_news_articles_published_at  (published_at)
ix_news_articles_category      (category)
ix_news_articles_country       (country)
```

Deduplication: `ON CONFLICT (url) DO NOTHING` — same article URL is never inserted twice.

## Security

| Layer | Config |
|-------|--------|
| Function auth | `--no-allow-unauthenticated` (403 to public) |
| Scheduler auth | OIDC token → `roles/run.invoker` on service account |
| Cloud SQL SSL | `requireSsl = true` |
| Cloud SQL network | `0.0.0.0/0` authorized (required for serverless; secured by SSL + password) |
| DB connection | Cloud SQL Python Connector via `IPTypes.PUBLIC` |

## Deploy Commands

### Redeploy function
```bash
cd functions/news_fetcher

gcloud functions deploy news-fetcher \
  --gen2 \
  --runtime=python312 \
  --region=asia-south1 \
  --project=vrittant-f5ef2 \
  --trigger-http \
  --no-allow-unauthenticated \
  --entry-point=fetch_news \
  --source=. \
  --set-env-vars="MEDIASTACK_KEY=<key>,DB_USER=postgres,DB_PASS=<pass>,DB_NAME=vrittant,INSTANCE_CONNECTION_NAME=vrittant-f5ef2:asia-south1:vrittant-db" \
  --timeout=60 \
  --memory=512Mi
```

### Update scheduler
```bash
# Delete and recreate
gcloud scheduler jobs delete news-fetcher-cron --location=asia-south1 --project=vrittant-f5ef2 --quiet

gcloud scheduler jobs create http news-fetcher-cron \
  --schedule="*/15 * * * *" \
  --uri="https://asia-south1-vrittant-f5ef2.cloudfunctions.net/news-fetcher" \
  --http-method=GET \
  --location=asia-south1 \
  --project=vrittant-f5ef2 \
  --time-zone="Asia/Kolkata" \
  --oidc-service-account-email="829303072442-compute@developer.gserviceaccount.com" \
  --oidc-token-audience="https://asia-south1-vrittant-f5ef2.cloudfunctions.net/news-fetcher"
```

### Manual trigger
```bash
gcloud scheduler jobs run news-fetcher-cron --location=asia-south1 --project=vrittant-f5ef2
```

### Check logs
```bash
gcloud functions logs read news-fetcher --gen2 --region=asia-south1 --project=vrittant-f5ef2 --limit=20
```

### Query articles via psql
```bash
# Start proxy
/opt/homebrew/bin/cloud-sql-proxy vrittant-f5ef2:asia-south1:vrittant-db --port 9471 &

# Connect
PGPASSWORD=<pass> psql -h 127.0.0.1 -p 9471 -U postgres -d vrittant

# Useful queries
SELECT count(*) FROM news_articles;
SELECT title, source, category, published_at FROM news_articles ORDER BY published_at DESC LIMIT 10;
SELECT category, count(*) FROM news_articles GROUP BY category ORDER BY count DESC;
```

## SQLAlchemy Model

The backend also has a corresponding model at `app/models/news_article.py` (imported in `app/main.py`). This is for future API endpoints that query the news_articles table — the Cloud Function creates the table independently via raw SQL.
