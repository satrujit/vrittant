# Sarvam cost analysis — query cookbook

Every Sarvam AI call (chat / translate / stt / tts / vision) writes one row
to `sarvam_usage_log`. The table is backend-only — there is no UI. Pull data
with `psql` over cloud-sql-proxy (port 5433):

```bash
# UAT
PGPASSWORD=$(gcloud secrets versions access latest --secret=DATABASE_URL --project=vrittant-f5ef2 \
  | sed -E 's|.*://postgres:([^@]+)@.*|\1|') \
  psql -h 127.0.0.1 -p 5433 -U postgres -d vrittant_uat

# Prod
PGPASSWORD=$(gcloud secrets versions access latest --secret=DATABASE_URL --project=vrittant-f5ef2 \
  | sed -E 's|.*://postgres:([^@]+)@.*|\1|') \
  psql -h 127.0.0.1 -p 5433 -U postgres -d vrittant
```

## How attribution works

Each row carries one of:

- **`story_id`** — the call was made for a specific story (categorisation,
  STT on uploaded audio, panel translate when the panel passes story_id,
  AI assists from the editor).
- **`bucket`** — the call has no story (yet) or none in principle:
  - `news_fetcher` — research/AI-generation in the news-articles flow
  - `widgets` — daily widget translation
  - `search` — query translation for cross-language search
  - `whatsapp_intake` — chitchat-vs-news classification on inbound WhatsApp
  - `dictation` — streaming STT WebSocket sessions
  - `reviewer_panel` — panel proxy calls without story_id (fallback)
- **Both `NULL`** — should not happen. Investigate via the
  `idx_sarvam_usage_unattributed` index (Q9 below).

## Pricing reconciliation

`cost_inr` is computed at write time from the static `PRICING` table in
`api/app/services/sarvam_client.py`. If Sarvam changes rates, **update
`PRICING` and the `_TRANSLATE_RATE_PER_10K` constant in
`widgets/widgets_core/translate.py`** — both must move together because the
widget service writes its rows directly (it doesn't import the API model).

Once a month: pull Q10 below, compare against the Sarvam invoice, alert
if drift > 2%.

## Queries

### Q1 — total cost in the last 30 days

```sql
SELECT
  date_trunc('day', created_at AT TIME ZONE 'Asia/Kolkata')::date AS day,
  ROUND(SUM(cost_inr), 2) AS inr
FROM sarvam_usage_log
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY day
ORDER BY day;
```

### Q2 — spend by bucket (this month)

```sql
SELECT
  COALESCE(bucket, '<story-attributed>') AS bucket,
  COUNT(*)                                 AS calls,
  ROUND(SUM(cost_inr), 2)                  AS inr
FROM sarvam_usage_log
WHERE created_at >= date_trunc('month', NOW())
GROUP BY bucket
ORDER BY inr DESC;
```

### Q3 — spend by service+model (this month)

```sql
SELECT
  service,
  model,
  COUNT(*)                  AS calls,
  ROUND(SUM(cost_inr), 2)   AS inr,
  ROUND(AVG(cost_inr), 4)   AS avg_per_call_inr
FROM sarvam_usage_log
WHERE created_at >= date_trunc('month', NOW())
GROUP BY service, model
ORDER BY inr DESC;
```

### Q4 — full lifecycle cost of one story

```sql
SELECT
  service, model, bucket,
  input_tokens, cached_tokens, output_tokens,
  characters, audio_seconds, pages,
  ROUND(cost_inr, 4) AS inr,
  created_at
FROM sarvam_usage_log
WHERE story_id = '<story-uuid>'
ORDER BY created_at;
```

And the rollup:

```sql
SELECT
  service,
  COUNT(*)                AS calls,
  ROUND(SUM(cost_inr), 4) AS inr
FROM sarvam_usage_log
WHERE story_id = '<story-uuid>'
GROUP BY service
ORDER BY inr DESC;
```

### Q5 — top 20 most expensive stories this month

```sql
SELECT
  l.story_id,
  s.headline,
  COUNT(*)                AS calls,
  ROUND(SUM(l.cost_inr), 2) AS inr
FROM sarvam_usage_log l
JOIN stories s ON s.id = l.story_id
WHERE l.created_at >= date_trunc('month', NOW())
GROUP BY l.story_id, s.headline
ORDER BY inr DESC
LIMIT 20;
```

### Q6 — average cost per story, by org

```sql
SELECT
  s.organization_id,
  COUNT(DISTINCT s.id)                          AS stories,
  ROUND(SUM(l.cost_inr), 2)                     AS total_inr,
  ROUND(SUM(l.cost_inr) / COUNT(DISTINCT s.id), 4) AS avg_inr_per_story
FROM sarvam_usage_log l
JOIN stories s ON s.id = l.story_id
WHERE l.created_at >= NOW() - INTERVAL '30 days'
GROUP BY s.organization_id
ORDER BY total_inr DESC;
```

### Q7 — which reviewer is burning the most translate budget?

```sql
SELECT
  user_id,
  COUNT(*)                AS calls,
  SUM(characters)         AS chars_translated,
  ROUND(SUM(cost_inr), 2) AS inr
FROM sarvam_usage_log
WHERE service = 'translate'
  AND created_at >= date_trunc('month', NOW())
  AND user_id IS NOT NULL
GROUP BY user_id
ORDER BY inr DESC
LIMIT 10;
```

### Q8 — failed call rate (something's wrong with Sarvam if this spikes)

```sql
SELECT
  date_trunc('hour', created_at AT TIME ZONE 'Asia/Kolkata')::timestamp AS hour,
  service,
  COUNT(*)                                   AS total,
  COUNT(*) FILTER (WHERE error IS NOT NULL)  AS failed,
  ROUND(100.0 * COUNT(*) FILTER (WHERE error IS NOT NULL) / COUNT(*), 1) AS pct_failed
FROM sarvam_usage_log
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY hour, service
HAVING COUNT(*) FILTER (WHERE error IS NOT NULL) > 0
ORDER BY hour DESC, pct_failed DESC;
```

### Q9 — unattributed calls (fix the call site!)

```sql
SELECT
  service, model, endpoint, COUNT(*), ROUND(SUM(cost_inr), 2) AS inr
FROM sarvam_usage_log
WHERE story_id IS NULL AND bucket IS NULL
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY service, model, endpoint
ORDER BY inr DESC;
```

### Q10 — monthly invoice reconciliation

```sql
SELECT
  date_trunc('month', created_at AT TIME ZONE 'Asia/Kolkata')::date AS month,
  service,
  ROUND(SUM(cost_inr), 2) AS our_computed_inr
FROM sarvam_usage_log
WHERE created_at >= date_trunc('month', NOW() - INTERVAL '2 months')
GROUP BY month, service
ORDER BY month DESC, our_computed_inr DESC;
```

Compare each row against the matching line in the Sarvam invoice. Drift
above ~2% means either:

1. Their pricing changed and we haven't updated `PRICING` yet, or
2. We have an unwrapped call site silently bypassing the ledger (grep for
   `api.sarvam.ai` outside `services/sarvam_client.py` and
   `widgets/widgets_core/translate.py`).
