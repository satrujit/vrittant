# vrittant-widgets

Standalone widget microservice. Daily-refreshed, plugin-based, read-only. Fully isolated from the main API and frontend.

## Architecture

```
fetcher/        Cloud Run Job — runs daily 00:30 IST via Cloud Scheduler
renderer/       Cloud Run Service — SSR HTML for iframe embedding
widgets_core/   Plugin ABC, registry, Firestore client, Sarvam translate, dedup
plugins/        One file per widget (drop in / remove freely)
templates/      Jinja2 templates, one per widget + _page.html wrapper
```

Storage: **Firestore** (no SQL).
- `widget_snapshots/{widgetId}_{YYYY-MM-DD}` — today's payload + rendered HTML
- `widget_served_items/{widgetId}/items/{hash}` — dedup ledger
- `widget_runs/{runId}` — fetch run audit log

## Adding a widget

1. Create `plugins/my_widget.py`:
   ```python
   from widgets_core import WidgetPlugin, register

   @register
   class MyWidget(WidgetPlugin):
       id = "my_widget"
       category = "misc"
       template = "my_widget.html"
       title_or = "ମୋର ୱିଜେଟ୍"
       dedup_strategy = "none"
       translate_fields = ["headline"]

       async def fetch(self) -> dict:
           return {"headline": "Hello from my widget"}
   ```
2. Create `templates/my_widget.html`.
3. Redeploy fetcher + renderer.

## Deploy

```bash
# one time
bash scripts/setup_iam.sh

# every change
bash scripts/deploy_renderer.sh
bash scripts/deploy_fetcher.sh
```

## Local dev

```bash
gcloud auth application-default login
bash scripts/run_fetcher_local.sh   # runs all plugins once and writes to real Firestore
bash scripts/run_renderer_local.sh  # http://localhost:8081/render/all
```

## Frontend embed

```jsx
<iframe
  src="https://widgets.vrittant.in/render/all"
  sandbox="allow-scripts allow-popups"
  referrerPolicy="no-referrer"
  style={{ width: "100%", height: 600, border: 0 }}
/>
```

The renderer sets `Content-Security-Policy: frame-ancestors` so only allow-listed origins can embed it. Iframe height is auto-managed via `postMessage({type:'vrittant-widget-resize', height})`.
