# Newspaper Widgets — Design

**Date:** 2026-04-17
**Status:** Approved → implementing

## Goal

Automated daily-refresh widgets (weather, panchang, gold/oil prices, gita verse, jokes, today-in-history, IPL points, fun facts, etc.) shown in the reviewer panel. Pluggable, isolated, no human curation, no admin UI, Odia-translated where applicable.

## Non-goals

- Print/IDML integration
- User-driven config
- Per-user personalisation
- Editing or curation surfaces

## Architecture

Standalone microservice repo `vrittant-widgets/` (lives inside the monorepo as a sibling of `api/` and `reviewer-panel/`).

```
vrittant-widgets/
├── widgets_core/          # plugin ABC, registry, dedup, firestore helpers
├── plugins/               # one .py per widget
├── templates/             # one .html per widget (Jinja2)
├── fetcher/               # Cloud Run Job — daily 00:30 IST cron
├── renderer/              # Cloud Run Service — SSR HTML
├── Dockerfile.fetcher
├── Dockerfile.renderer
└── requirements.txt
```

### Storage — Firestore (no SQL)

- `widget_snapshots/{widgetId}_{YYYY-MM-DD}` — today's payload + rendered HTML
- `widget_served_items/{widgetId}/items/{contentHash}` — dedup ledger
- `widget_runs/{runId}` — fetch run audit log

### Two services

| Service | Type | Trigger | Job |
|---|---|---|---|
| `widget-fetcher` | Cloud Run Job | Cloud Scheduler `30 0 * * *` IST | discover plugins → fetch in parallel → translate via Sarvam → dedup → write snapshot |
| `widget-renderer` | Cloud Run Service | HTTP | reads today's snapshot → returns SSR HTML page; sets CSP `frame-ancestors` |

### Plugin contract

```python
@register
class GitaVerseWidget(WidgetPlugin):
    id = "gita_verse"
    category = "spiritual"
    template = "gita_verse.html"
    schedule = "30 0 * * *"
    dedup_strategy = "unique_forever"
    translate_fields = ["text", "meaning"]

    async def fetch(self) -> dict:
        ...
```

Dedup strategies: `none`, `deterministic`, `unique_within_days`, `unique_forever`.

### Frontend integration

One iframe, sandboxed:

```jsx
<iframe
  src="https://widgets.vrittant.in/render/all"
  sandbox="allow-scripts allow-popups"
  referrerPolicy="no-referrer"
/>
```

Renderer sets `Content-Security-Policy: frame-ancestors https://vrittant.in https://*.vrittant.in`.
Iframe height handled via `postMessage({type:'widget-resize', height})` with parent-side origin check.

### Security boundary

- `sandbox` blocks: cookies/localStorage of parent, `parent.window` access, top-nav, form posts, popups beyond `allow-popups`.
- `frame-ancestors` blocks clickjacking from any other origin.
- Renderer is read-only — no user-provided input ever reaches it.
- Plugins run in fetcher only, never on render path.

### Plugins (initial 5, more later)

| ID | Source | Dedup |
|---|---|---|
| `weather` | Open-Meteo | none |
| `gita_verse` | Bhagavad Gita API | unique_forever |
| `today_in_history` | Muffinlabs | deterministic (date-keyed) |
| `joke` | JokeAPI | unique_within_days=90 |
| `gold_oil_prices` | metals.live + Frankfurter | none |

Future: panchang, IPL points, NASA APOD, fun fact, quote-of-day, currency, weather-7day, district events.

## Resilience

- Each plugin fetch wrapped in `asyncio.wait_for(timeout=30)`.
- Plugin failure logged + previous day's snapshot kept (`/render` falls back to most recent snapshot ≤ 7d old).
- Job exits 0 unless ALL plugins fail.

## Cost

~$5–50/month (Cloud Run scale-to-zero, Firestore free tier covers daily writes for ~50 widgets).
