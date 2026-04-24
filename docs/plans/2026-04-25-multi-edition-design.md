# Multi-Edition Per Day — Design

**Status:** approved 2026-04-25
**Audience:** anyone implementing the daily-edition auto-creation + matrix
assignment UI for Pragativadi (and any future multi-edition newspaper org).

## Goal

Pragativadi publishes 6 editions of the print paper per day plus a Sunday-only
supplement called Avimat. The current product assumes one edition per day,
created and populated by hand. We want:

1. The day's editions to be created automatically every morning, with the
   right page templates per edition.
2. A reviewer to be able to assign a single story across multiple editions
   in one interaction (instead of 5–7 round-trips through the existing
   per-edition dropdown).

The same set of stories typically goes into most editions of a given day,
but each edition can diverge — geographically (a Bhubaneswar-only page) or
because of ad load (low-priority stories dropped). Both directions need to
be cheap.

## Non-goals

- Layout / pagination automation. We're routing stories to pages, not
  flowing them into a printable PDF.
- Auto-routing by category or AI. The system stays editor-driven; we make
  the editor's clicks fewer, not optional.
- Capacity enforcement / overflow handling. Capacity hints were considered
  and dropped for v1; pages are uncapped.
- Real-time multi-cursor sync. The matrix and bucket view are kept
  consistent through React Query cache invalidation; cross-tab editing
  resolves on next focus/refetch. Newspaper editing isn't a Google Doc.

## Current state (where we're starting from)

Schema lives in `api/app/models/edition.py`:

```
Edition (id, organization_id, publication_date, paper_type, title, status)
  └── EditionPage (id, edition_id, page_number, page_name, sort_order)
        └── EditionPageStory (id, edition_page_id, story_id, sort_order)
```

The `EditionPageStory` join table has no unique constraint on `story_id`,
so the same story already can sit on multiple pages and multiple editions
— good, the data model already supports the use case.

Editions are created by a reviewer through `POST /admin/editions` in
`api/app/routers/editions/write.py`. For `paper_type == "daily"` the
endpoint seeds pages from `OrgConfig.page_suggestions`.

Stories are placed on pages from two surfaces today:

- **Bucket view** (`reviewer-panel/src/pages/BucketDetailPage.jsx`) —
  drag-and-drop within an edition.
- **Story right-side panel** (`reviewer-panel/src/components/review/ReviewSidePanel.jsx`)
  — two dropdowns ("Choose edition…" → "Choose page…") plus an Assign
  button. Assigns to one edition × one page per click.

Recurring jobs run via Cloud Scheduler → `POST /internal/<thing>` with a
shared `X-Internal-Token` header. Pattern is well established
(`internal.py`, `widgets/`).

There is no concept today of named/templated editions per weekday, no
A/B/C/D pages, no Avimat.

## Design

### 1. Data model

Single new column + one new JSON config field. Everything else reuses
existing structure.

**`OrgConfig.edition_schedule`** — new JSON column. Per-org list of
edition templates, each carrying its weekday filter and its page list.
Shape:

```json
[
  {
    "name": "Ed 1",
    "weekdays": [0, 1, 2, 3, 4, 5],
    "pages": [
      {"page_number": 1, "page_name": "pg_1"},
      {"page_number": 2, "page_name": "pg_2"},
      ...
      {"page_number": 12, "page_name": "pg_12"}
    ]
  },
  {
    "name": "Ed 2",
    "weekdays": [0, 1, 2, 3, 4, 5],
    "pages": [
      {"page_number": 1, "page_name": "pg_1"},
      ...
      {"page_number": 12, "page_name": "pg_12"},
      {"page_number": 13, "page_name": "pg_A"},
      {"page_number": 14, "page_name": "pg_B"},
      {"page_number": 15, "page_name": "pg_C"},
      {"page_number": 16, "page_name": "pg_D"}
    ]
  },
  ... (Ed 3, 4, 5 identical to Ed 2)
  {
    "name": "Ed 6",
    "weekdays": [0, 1, 2, 3, 4, 5],
    "pages": [
      {"page_number": 1, "page_name": "pg_1"},
      ...
      {"page_number": 16, "page_name": "pg_16"}
    ]
  },
  {
    "name": "Avimat",
    "weekdays": [6],
    "pages": [
      {"page_number": 1, "page_name": "pg_1"},
      ...
      {"page_number": 10, "page_name": "pg_10"}
    ]
  }
]
```

Weekdays use Python's `datetime.weekday()` convention: Mon=0…Sun=6.

If `edition_schedule` is empty/null for an org, the auto-create job is a
no-op for that org (preserves today's behavior for everyone except
Pragativadi).

**No new columns on `Edition` or `EditionPage`.** A/B/C/D pages live as
ordinary `EditionPage` rows distinguished only by `page_name`. The matrix
UI surfaces `page_name`, never `page_number`. Page A ends up with
`page_number = 13` (which is what makes it sort after page 12) but is
displayed as `pg_A`. Edition 6 has page_numbers 13–16 with names
`pg_13`–`pg_16`.

**Edition uniqueness.** Add a unique index on `(organization_id,
publication_date, title)` so the auto-create job is naturally idempotent
— rerunning it the same day inserts nothing.

### 2. Auto-create scheduled job

New endpoint:

```
POST /internal/seed-todays-editions
Header: X-Internal-Token: <shared secret>
Body: (none, or {"date": "YYYY-MM-DD"} for backfill testing)
```

Logic:

1. Resolve target date (default: today in IST).
2. For each `Organization` with non-empty `OrgConfig.edition_schedule`:
3. For each template in `edition_schedule` whose `weekdays` contains the
   target date's weekday:
4. If an `Edition` already exists for `(org_id, date, name)`, skip.
   Otherwise insert the Edition row and seed its `EditionPage` rows from
   the template.
5. Return `{created: [...], skipped: [...]}` summary.

Hook up Cloud Scheduler at **00:05 IST daily** to call the endpoint with
the shared token.

The existing manual `POST /admin/editions` endpoint stays unchanged for
ad-hoc supplements / one-off editions.

### 3. Matrix assignment UI

Replaces the current single-edition dropdown in
`ReviewSidePanel.jsx`. Cells are minimal — page name + drop indicator —
no icons, no section names, no capacity dot.

```
Quick:  [All daily]  [Clear]

       Ed 1     Ed 2     Ed 3     Ed 4     Ed 5     Ed 6     Avimat
      ┌──────┬─┬──────┬─┬──────┬─┬──────┬─┬──────┬─┬──────┬─┬──────┐
      │ pg_3 │ │ pg_3 │ │ pg_3 │ │ pg_5 │ │ pg_3 │ │ pg_3 │ │  —   │
      └──────┴─┴──────┴─┴──────┴─┴──────┴─┴──────┴─┴──────┴─┴──────┘
```

Behaviors:

- **Cell content** = `page_name` of the edition_page this story is
  currently placed on, OR `—` when the story is not placed in that
  edition.
- **Click cell** → small popover lists the edition's pages by
  `page_name`. Choosing a page either creates a new placement or moves
  an existing one. A "Drop from this edition" option removes the
  placement.
- **Fan-out by page_name match.** When the user picks a page in any
  cell, every other daily edition's cell that hasn't been manually
  overridden gets the page in *its own* edition whose `page_name`
  matches. If an edition has no matching page_name, that cell stays as
  it was. Avimat is excluded from fan-out.
- **Override tracking.** Once the user explicitly clicks a cell to set
  a page (or drop), that cell is "manually overridden" for the rest of
  this editing session and is not touched by subsequent fan-outs.
  This is local UI state — not persisted.
- **Quick presets:**
  - `[All daily]` — for each daily edition (Ed 1…Ed 6 in order), set the
    story's placement to whichever page matches the most recent picked
    page_name (or `pg_1` if nothing has been picked yet). Avimat is
    untouched.
  - `[Clear]` — drop the story from every edition (matrix becomes all
    `—`).
- **Avimat** — the cell is always present when an Avimat edition exists
  for the date. It only ever changes when the user clicks it directly.

### 4. Bulk-assignment endpoint

```
PUT /admin/stories/{story_id}/placements
Body: { "placements": [{"edition_id": "...", "page_id": "..."}, ...] }
```

Server-side: diff against the story's current `edition_page_stories`
rows, insert the missing ones, delete the missing-from-the-new-set ones,
return the resulting placement list. All in one transaction.

The existing per-page endpoints
(`POST /admin/editions/{id}/pages/{page_id}/stories`,
`DELETE /admin/editions/{id}/pages/{page_id}/stories/{story_id}`) stay
untouched — the bucket view's drag-drop continues to use them.

### 5. Bidirectional sync between matrix and bucket view

Single source of truth = the database, surfaced via React Query cache.

- The matrix queries (and mutates) under cache key
  `['story', storyId, 'placements']` and reads the per-edition pages
  list under `['edition', editionId, 'pages']`.
- The bucket view already reads `['edition', editionId, 'pages']`.
- A matrix mutation invalidates `['story', storyId, 'placements']` plus
  every `['edition', editionId, 'pages']` it touched.
- A bucket-view drag mutation invalidates `['edition', editionId,
  'pages']` plus `['story', storyId, 'placements']` for the dragged
  story.
- React Query's `refetchOnWindowFocus` (already on) handles the
  cross-tab case on the next focus event.

No websockets, no polling. v1.

## Open follow-ups (deferred, not in v1)

- **Capacity per page.** Soft cap + green/amber/red dot in each cell.
  Dropped from v1 to keep scope tight; revisit when editors ask for it.
- **Section-aware fan-out.** Fan out by category-section pairing instead
  of page_name match. Requires per-edition `section → page` mapping in
  the template.
- **AI-suggested overrides.** "Story mentions Bhubaneswar twice → pre-
  suggest Edition 4 page pg_5_BBSR." Sits on top of the matrix as a
  one-click accept.
- **Edition status automation.** Auto-finalize editions at a configured
  cutoff time, lock placements, etc.

## Risks / things to watch in implementation

- **Existing `OrgConfig.page_suggestions`** stays for now — manual edition
  creation for non-daily paper types still uses it. Don't delete it
  until we're sure no org depends on the manual flow.
- **Migrating Pragativadi's current single-edition habit.** Once the
  auto-create job runs, every weekday will produce 6 editions and Sunday
  will produce 1 Avimat. Existing in-progress editions for today must be
  handled (likely: leave them alone, future days get the new behavior).
- **Cache invalidation correctness** is the main bug surface for the
  bidirectional-sync claim. Test that a bucket-view drag updates the
  matrix on the same screen within one render cycle.
- **Idempotency** of the seed endpoint must be airtight — Cloud
  Scheduler retries on failure, and we don't want duplicate editions.

## Implementation handoff

A concrete task-by-task implementation plan goes in
`docs/plans/2026-04-25-multi-edition.md` (forthcoming, via the
writing-plans skill).
