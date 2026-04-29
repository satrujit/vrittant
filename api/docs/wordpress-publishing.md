# WordPress auto-publish

Approved Vrittant stories are translated to English and pushed to the
org's WordPress site as `status=draft`. The WP team reviews from the
WP admin and decides Publish / Trash. Status flows back to Vrittant
via the same sweep so editors here see the lifecycle.

## How it works

1. Editor approves a story in Vrittant. Status hook flips
   `stories.wp_push_status = 'pending'` (no other state changes).
2. Cloud Scheduler hits `POST /internal/sweep-wp-push` every 60 s.
   The sweep batch (10 stories) translates each via Claude Haiku and
   creates a WP post via `POST /wp-json/wp/v2/posts` with
   `status=draft`. The new WP post id is stamped on the story.
3. If the editor edits the story after the first push, the save flips
   `wp_push_status = 'pending'` again. The next sweep tick GETs the
   post on the WP side; if it's still `draft`, it updates in place; if
   it's anything else (`publish`, `pending`, `private`, `trash`), the
   sweep marks the story `skipped_wp_status_<x>` and stops touching
   it — the WP team owns the post once they've moved it past `draft`.
4. If a story is un-approved (status flips back to `flagged`,
   `rejected`, or `submitted` from `approved`), the sweep moves the WP
   draft to trash. Already-published posts are NOT auto-unpublished —
   the editor sees a chip telling them to retract manually.

## Configuration (per org)

Stored on `org_configs.wordpress_config` as JSON. Set with:

```sql
UPDATE org_configs
SET wordpress_config = jsonb_build_object(
  'base_url',             'https://pragativadi.com',
  'username',             'vrittant-bot',
  'app_password_secret',  'WP_PRAGATIVADI_APP_PASSWORD',
  'default_author_id',    12,
  'default_status',       'draft',
  'category_map', jsonb_build_object(
    'crime',         5,
    'politics',      8,
    'sports',       14,
    'governance',   17,
    'entertainment', 21,
    'accident',     23,
    'science',      24,
    'general',      26
  )
)
WHERE organization_id = 'org-pragativadi-prod';
```

The actual app password lives in **Secret Manager**, not in the DB:

```bash
echo -n "<app password copied from WP profile>" | \
  gcloud secrets create WP_PRAGATIVADI_APP_PASSWORD \
    --project=vrittant-f5ef2 --data-file=-
```

Then expose to the API service via `--set-secrets`. Append the line
below to **both** `.github/workflows/deploy-uat.yml` and
`.github/workflows/deploy-prod.yml` (inside the existing `--set-secrets`
flag, comma-separated):

```
WP_PRAGATIVADI_APP_PASSWORD=WP_PRAGATIVADI_APP_PASSWORD:latest
```

After the next deploy, the secret is available as an env var with the
same name; `_load_wp_config()` reads it via `os.environ`.

If `wordpress_config` is empty / missing / its referenced secret isn't
set, the sweep marks each affected story with
`wp_push_status = 'skipped_no_config'` and moves on — no errors, no
backlog.

## Cloud Scheduler

Create one job per environment. Run once each, after the first deploy:

```bash
# UAT
gcloud scheduler jobs create http vrittant-wp-push-uat \
  --project=vrittant-f5ef2 \
  --location=asia-south1 \
  --schedule="* * * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://vrittant-api-uat-829303072442.asia-south1.run.app/internal/sweep-wp-push" \
  --http-method=POST \
  --headers="X-Internal-Token=<value of INTERNAL_TOKEN secret>" \
  --attempt-deadline=120s

# Prod
gcloud scheduler jobs create http vrittant-wp-push-prod \
  --project=vrittant-f5ef2 \
  --location=asia-south1 \
  --schedule="* * * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://vrittant-api-829303072442.asia-south1.run.app/internal/sweep-wp-push" \
  --http-method=POST \
  --headers="X-Internal-Token=<value of INTERNAL_TOKEN secret>" \
  --attempt-deadline=120s
```

Pull the token with:

```bash
gcloud secrets versions access latest --secret=INTERNAL_TOKEN --project=vrittant-f5ef2
```

(If the existing STT / categorisation Cloud Scheduler jobs use a
different schedule cadence, follow their pattern. 60 s is fine for
1–10 approvals/min; bump if approvals spike.)

## Observability

The sweep response is the canonical health metric:

```
POST /internal/sweep-wp-push  →  {
  "picked": 3,         // stories pulled this tick
  "ok": 2,
  "failed": 1,
  "skipped": 0,
  "exhausted": 0       // stories that hit MAX_ATTEMPTS this tick
}
```

`picked` rising over many ticks = pushes are slower than approvals.
`exhausted` rising = WP is unhealthy or auth is wrong.

Each row carries `wp_push_error` for the editor (and in the side panel
chip's tooltip).

## Manual operations

Force-retry a stuck row:

```sql
UPDATE stories SET wp_push_status='pending', wp_push_attempts=0, wp_push_error=NULL
WHERE id = '<story-id>';
```

Force-retract (if WP team can't find the draft):

```sql
UPDATE stories SET wp_push_status='retract', wp_push_attempts=0, wp_push_error=NULL
WHERE id = '<story-id>';
```

Inspect a story's WP state:

```sql
SELECT id, headline, status, wp_post_id, wp_url, wp_push_status,
       wp_push_attempts, wp_push_error, wp_pushed_at
FROM stories WHERE id = '<story-id>';
```
