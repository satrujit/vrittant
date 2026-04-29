# WordPress Integration — Activation Checklist

**Status:** dormant on prod (commit `e54a823`, deployed 2026-04-29).
Schema, code, sweep endpoint, UI, and tests are all live; the
integration is waiting on WP-side credentials. Once the WP team sends
the items from `docs/WORDPRESS_TEAM_REQUIREMENTS.md`, run through this
checklist top to bottom.

> **Goal:** flip from `wp_push_status='skipped_no_config'` to live
> drafts appearing in the WP admin within 60 seconds of an approval,
> with zero downtime and no other side effects.

---

## What you should have in hand

Filled in by the WP-side administrator (use the form at the bottom of
`docs/WORDPRESS_TEAM_REQUIREMENTS.md`):

- [ ] WordPress base URL — e.g. `https://pragativadi.com`
- [ ] Bot WP **username** — e.g. `vrittant-bot`
- [ ] **Application Password** — 24 chars (treat like a secret)
- [ ] Bot WP **user ID** — integer
- [ ] **Category map** — Vrittant key → WP category id, for at least
      `crime`, `politics`, `sports`, `governance`, `entertainment`,
      `accident`, `science`, `general`
- [ ] Default post status — usually `draft`, sometimes `pending`

If any are missing, ping back; don't guess.

---

## Step 1 — Store the password in Secret Manager

One per org. Replace `PRAGATIVADI` with the org slug-cap if it's a
different publisher (e.g. `WP_SAMBAD_APP_PASSWORD`).

```bash
echo -n "<APP_PASSWORD_FROM_WP>" | \
  gcloud secrets create WP_PRAGATIVADI_APP_PASSWORD \
    --project=vrittant-f5ef2 --data-file=-
```

Verify it exists:

```bash
gcloud secrets versions access latest \
  --secret=WP_PRAGATIVADI_APP_PASSWORD --project=vrittant-f5ef2
```

(Should echo the password back — that's how the API will read it.)

---

## Step 2 — Wire the secret into Cloud Run

Edit **both** deploy workflows; append to the existing `--set-secrets`
flag (comma-separated, no spaces):

- `.github/workflows/deploy-uat.yml`
- `.github/workflows/deploy-prod.yml`

```diff
-  --set-secrets="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=...,..."
+  --set-secrets="DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=...,...,WP_PRAGATIVADI_APP_PASSWORD=WP_PRAGATIVADI_APP_PASSWORD:latest"
```

Commit + push to `develop` (which auto-deploys UAT) — verify the env
var lands on the new revision:

```bash
gcloud run services describe vrittant-api-uat \
  --region=asia-south1 --project=vrittant-f5ef2 \
  --format='value(spec.template.spec.containers[0].env)' \
  | tr ',' '\n' | grep WP_PRAGATIVADI
```

Then merge `develop → main` to deploy prod.

---

## Step 3 — Configure the org in the database

UAT first, then prod. Run via the cloud-sql-proxy already in use for
schema migrations.

```sql
UPDATE org_configs
SET wordpress_config = jsonb_build_object(
  'base_url',             'https://pragativadi.com',
  'username',             'vrittant-bot',
  'app_password_secret',  'WP_PRAGATIVADI_APP_PASSWORD',
  'default_author_id',    12,           -- bot WP user id
  'default_status',       'draft',
  'category_map', jsonb_build_object(
    'crime',          5,
    'politics',       8,
    'sports',        14,
    'governance',    17,
    'entertainment', 21,
    'accident',      23,
    'science',       24,
    'general',       26
  )
)
WHERE organization_id = 'org-pragativadi-prod';
```

For UAT use `WHERE organization_id = 'org-pragativadi'`.

---

## Step 4 — Smoke test before turning the cron on

Pick one already-approved story whose `wp_push_status` is currently
`skipped_no_config` and reset it:

```sql
SELECT id, headline, wp_push_status FROM stories
 WHERE organization_id = 'org-pragativadi-prod'
   AND status = 'approved'
   AND wp_push_status = 'skipped_no_config'
 ORDER BY created_at DESC LIMIT 1;
-- copy the id

UPDATE stories
   SET wp_push_status = 'pending', wp_push_attempts = 0, wp_push_error = NULL
 WHERE id = '<that-id>';
```

Then call the sweep endpoint manually once:

```bash
TOKEN=$(gcloud secrets versions access latest --secret=INTERNAL_TOKEN --project=vrittant-f5ef2)
curl -sS -X POST \
  -H "X-Internal-Token: $TOKEN" \
  https://vrittant-api-829303072442.asia-south1.run.app/internal/sweep-wp-push
# expect: {"picked":1,"ok":1,"failed":0,"skipped":0,"exhausted":0}
```

Verify the row updated:

```sql
SELECT id, wp_post_id, wp_url, wp_push_status, wp_pushed_at, wp_push_error
  FROM stories WHERE id = '<that-id>';
```

You should see `wp_push_status='ok'` and a real `wp_url`. Open the
URL in a browser — the WP admin should show a draft with the English
translation and (if the story had a photo) a featured image.

If it's `skipped_no_config` still: secret didn't land — re-check
Step 2's deploy actually rolled the new revision. If it's `failed`:
read `wp_push_error` — usually auth (wrong password) or category id
mismatch.

---

## Step 5 — Register Cloud Scheduler

```bash
TOKEN=$(gcloud secrets versions access latest --secret=INTERNAL_TOKEN --project=vrittant-f5ef2)

# UAT
gcloud scheduler jobs create http vrittant-wp-push-uat \
  --project=vrittant-f5ef2 \
  --location=asia-south1 \
  --schedule="* * * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://vrittant-api-uat-829303072442.asia-south1.run.app/internal/sweep-wp-push" \
  --http-method=POST \
  --headers="X-Internal-Token=$TOKEN" \
  --attempt-deadline=120s

# Prod
gcloud scheduler jobs create http vrittant-wp-push-prod \
  --project=vrittant-f5ef2 \
  --location=asia-south1 \
  --schedule="* * * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://vrittant-api-829303072442.asia-south1.run.app/internal/sweep-wp-push" \
  --http-method=POST \
  --headers="X-Internal-Token=$TOKEN" \
  --attempt-deadline=120s
```

Check it runs:

```bash
gcloud scheduler jobs run vrittant-wp-push-prod \
  --location=asia-south1 --project=vrittant-f5ef2
gcloud logging read \
  'resource.type="cloud_run_revision" AND textPayload=~"sweep-wp-push"' \
  --project=vrittant-f5ef2 --limit=5
```

---

## Step 6 — Backfill the previously-skipped stories (optional)

When `wordpress_config` was missing, every approved story got
`skipped_no_config`. If you want those backfilled into WP:

```sql
UPDATE stories
   SET wp_push_status = 'pending', wp_push_attempts = 0, wp_push_error = NULL
 WHERE organization_id = 'org-pragativadi-prod'
   AND wp_push_status = 'skipped_no_config'
   AND status = 'approved'
   AND deleted_at IS NULL;
```

The cron will pick them up at 10/minute and drain over the next hour
or so. Watch the queue:

```sql
SELECT wp_push_status, count(*) FROM stories
 WHERE organization_id = 'org-pragativadi-prod'
 GROUP BY 1 ORDER BY 2 DESC;
```

If you'd rather only push **future** approvals (not reprocess history),
skip this step.

---

## Step 7 — Confirm with the WP team

- They should see new drafts appearing in **Posts → Drafts**.
- Have them publish one to validate the round-trip: Vrittant editor's
  "WordPress" chip should flip from green ("Sent to website") to
  blue ("Live on website") with a clickable link, within ~60 seconds
  of their Publish click.
- Have them trash one to validate the retract direction: the chip
  should read "Rejected by website".

Both transitions are pull-only (Vrittant polls WP-side `status` on
each subsequent edit). No webhooks needed.

---

## Operational notes (post-activation)

- Manual retry of a failed push:
  ```sql
  UPDATE stories SET wp_push_status='pending', wp_push_attempts=0, wp_push_error=NULL
   WHERE id = '<story-id>';
  ```
- Manual retract (force-trash on WP if it's still draft):
  ```sql
  UPDATE stories SET wp_push_status='retract', wp_push_attempts=0, wp_push_error=NULL
   WHERE id = '<story-id>';
  ```
- Rotate the WP password: generate a new Application Password in WP →
  add a new version of the secret (`gcloud secrets versions add ...`)
  → next sweep tick reads it. No deploy needed.
- Disable: drop the Cloud Scheduler job. Existing pending rows freeze
  but no longer process. Re-enabling resumes from where it stopped.

## Reference

- Architecture + code map: `api/docs/wordpress-publishing.md`
- WP-team setup form: `docs/WORDPRESS_TEAM_REQUIREMENTS.md`
- Service code: `api/app/services/wordpress_publisher.py`
- Sweep endpoint: `api/app/routers/internal.py::sweep_wp_push`
- Tests: `api/tests/test_wordpress_publisher.py`
