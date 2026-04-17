# vrittant-widgets

Plugin-based daily widget fetcher. Writes consolidated snapshots to Postgres; the reviewer panel reads them via `GET /api/widgets/all` and renders natively in React.

## Architecture

```
fetcher/        Cloud Run Job — runs daily 00:30 IST via Cloud Scheduler
widgets_core/   Plugin ABC, registry, DB client, Sarvam translate, dedup
plugins/        One file per widget (drop in / remove freely)
```

Storage: **Postgres** (`widgets.snapshots` — one row per widget per day).

## Adding a widget

1. Create `plugins/my_widget.py`:
   ```python
   from widgets_core import WidgetPlugin, register

   @register
   class MyWidget(WidgetPlugin):
       id = "my_widget"
       category = "misc"
       title_or = "ମୋର ୱିଜେଟ୍"
       dedup_strategy = "none"
       translate_fields = ["headline"]

       async def fetch(self) -> dict:
           return {"headline": "Hello from my widget"}
   ```
2. Add a matching React renderer in `reviewer-panel/src/pages/WidgetsPage.jsx` (CATALOG entry).
3. Redeploy the fetcher.

## Deploy

```bash
# one time
bash scripts/setup_iam.sh

# every change
bash scripts/deploy_fetcher.sh
```

## Local dev

```bash
gcloud auth application-default login
bash scripts/run_fetcher_local.sh   # runs all plugins once and writes to Postgres
```
