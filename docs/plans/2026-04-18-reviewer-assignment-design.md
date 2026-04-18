# Reviewer Assignment — Design

**Date:** 2026-04-18
**Status:** Approved (ready for implementation plan)

## Goal

Auto-assign every newly submitted story to a specific reviewer based on category and region beats, while letting anyone reassign in one click from the dashboard. Eliminates the "who picks this up?" coordination cost without removing human override.

## Principles

- **Always lands on a reviewer.** No story stays orphaned and no admin fallback queue. The algorithm degrades gracefully through three steps and ends at "least-loaded reviewer overall."
- **Auto is a default, not a lock.** Anyone (any active reviewer or org admin) can reassign. Auto-assignment buys time; humans correct misroutes.
- **Reporters file, reviewers review.** Reporters never receive assignments. The role split is preserved.
- **Single source of truth for categories.** Reviewer category beats and story categories both pull from `OrgConfig.categories` (the existing per-org master list shared with mobile + web).
- **YAGNI.** No notifications, no bulk-reassign UI, no rebalance-on-beat-change, no story backfill in v1.

## Data Model

### `User` (extend)

| Column | Type | Notes |
|--------|------|-------|
| `categories` | JSON `list[str]`, default `[]` | Only meaningful for `user_type='reviewer'`. Each entry must be a valid key from `OrgConfig.categories`. |
| `regions` | JSON `list[str]`, default `[]` | Only meaningful for `user_type='reviewer'`. Free-text tags; matched against `reporter.area_name` after normalization. |
| `area_name` | existing column | Becomes **required** when `user_type='reporter'` (DB-level NOT NULL after pre-flight; API-level required validator immediately). |

### `Story` (extend)

| Column | Type | Notes |
|--------|------|-------|
| `assigned_to` | FK → `users.id`, indexed, nullable | Set at story-submit time by `pick_assignee()`. Nullable only for historic rows pre-migration. |
| `assigned_match_reason` | VARCHAR, nullable | Enum: `'category'`, `'region'`, `'load_balance'`, `'manual'`. Drives the dashboard badge. |

### `StoryAssignmentLog` (new)

| Column | Type |
|--------|------|
| `id` | PK |
| `story_id` | FK → stories.id, indexed |
| `from_user_id` | FK → users.id, nullable (null = first auto-assign) |
| `to_user_id` | FK → users.id |
| `assigned_by` | FK → users.id, nullable (null = system auto-assign) |
| `reason` | enum: `'auto'`, `'manual'`, `'reviewer_deactivated'` |
| `created_at` | timestamp |

## Assignment Algorithm

`pick_assignee(story, db) -> (User, reason)` — pure function, single transaction, always returns a reviewer.

```
def pick_assignee(story, db):
    reviewers = active reviewers in story.organization

    # Step 1 — category match (skip "general" / null)
    if story.category and story.category != "general":
        candidates = [r for r in reviewers if story.category in r.categories]
        if candidates:
            return least_loaded(candidates), "category"

    # Step 2 — region match
    reporter_area = normalize(story.reporter.area_name)
    if reporter_area:
        candidates = [
            r for r in reviewers
            if any(normalize(rg) == reporter_area for rg in r.regions)
        ]
        if candidates:
            return least_loaded(candidates), "region"

    # Step 3 — overall fallback
    return least_loaded(reviewers), "load_balance"
```

**Helpers:**
- `normalize(s)`: `s.strip().lower()`, also strips a trailing `" district"` suffix.
- `least_loaded(users)`: SELECT `COUNT(*) FROM stories WHERE assigned_to=? AND status NOT IN ('published','rejected')` per candidate; pick min. Tie → lowest `user.id` (deterministic).

**Edge case — zero reviewers in org:** raise; story is created with `assigned_to=null` and the dashboard surfaces an empty-state banner pointing admin at user settings. Submit still succeeds.

**Call sites:**
1. Story-create endpoint (reporter submit) — synchronous within the same transaction; writes the first `StoryAssignmentLog` row with `from_user_id=null, assigned_by=null, reason='auto'`.
2. Reviewer-deactivation endpoint — re-runs over all open stories where `assigned_to=deactivated_user.id`. Each reassign writes a log row with `reason='reviewer_deactivated'`.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST /admin/stories` | (existing) extend to call `pick_assignee()` after row create; response includes `assigned_to`. |
| `PATCH /admin/stories/{id}/assignee` | New. Body `{ "assignee_id": "<user_id>" }`. Auth: any active reviewer or admin. Sets `assigned_match_reason='manual'`. Writes log row. |
| `GET /admin/stories` | (existing) extend with `assigned_to` query param accepting a user_id, the literal `"me"`, or omitted = all. Response rows gain `assigned_to`, `assigned_to_name`, `assigned_match_reason`. |
| `GET /admin/stories/{id}/assignment-log` | New. Returns full audit timeline newest-first. |
| `PATCH /admin/users/{id}` | (existing) extend to accept `categories: list[str]` and `regions: list[str]` (validated only when `user_type='reviewer'`); validate categories against `OrgConfig.categories`. Enforce required `area_name` when `user_type='reporter'`. |
| `PATCH /admin/users/{id}/deactivate` | (existing) after marking inactive, run redistribution loop. |
| `GET /admin/users?role=reviewer&active=true` | (existing — confirm filter support) used by inline reassign dropdown. |

## Frontend

### Dashboard (stories list)

- New filter control: **assignee dropdown** with `Assigned to me` (default), each reviewer name, and `All`. Persists to URL query (`?assigned_to=me|<id>|all`).
- Each row gains an **Assignee column**:
  - Inline shadcn `Select` with avatar/initial + reviewer name. On change → `PATCH /admin/stories/{id}/assignee` (optimistic UI + toast).
  - Below the name, a small muted badge from `assigned_match_reason`: `📂 Sports`, `📍 Koraput`, `⚖️ Load balance`, or `✏️ Manual`.
- Empty state when org has zero reviewers: info banner pointing at user settings.

### Review page

- Header gains the same inline assignee dropdown + badge.
- "Assignment history" link/drawer → renders `GET /admin/stories/{id}/assignment-log` as a vertical timeline (`from → to`, by whom, when, reason).

### Admin user-edit form (in `SettingsPage`, existing user/entitlements section)

- When `user_type === 'reviewer'`, two new controls below entitlements:
  - **Categories** — multi-select chips from `OrgConfig.categories` (active only).
  - **Regions** — free-text tag input (Enter to add, Backspace to remove).
- When `user_type === 'reporter'`, `area_name` becomes required (red asterisk + validation).
- Reviewer deactivation submit → confirmation modal: *"This will redistribute N open stories to other reviewers. Continue?"*

### i18n keys (add to `en.json`, `or.json`, `hi.json`)

`assignment.assignedToMe`, `assignment.allReviewers`, `assignment.reasonCategory`, `assignment.reasonRegion`, `assignment.reasonLoadBalance`, `assignment.reasonManual`, `assignment.reassignSuccess`, `assignment.history`, `assignment.deactivateConfirm`, `userForm.categoriesLabel`, `userForm.regionsLabel`, `userForm.areaRequired`.

## Migration & Rollout

**DB migration via cloud-sql-proxy** (Cloud Run `create_all` won't add columns to existing tables):

1. `ALTER TABLE users ADD COLUMN categories JSON NOT NULL DEFAULT '[]'::json;`
2. `ALTER TABLE users ADD COLUMN regions JSON NOT NULL DEFAULT '[]'::json;`
3. `ALTER TABLE stories ADD COLUMN assigned_to VARCHAR REFERENCES users(id);`
4. `ALTER TABLE stories ADD COLUMN assigned_match_reason VARCHAR;`
5. `CREATE INDEX ix_stories_assigned_to ON stories(assigned_to);`
6. `CREATE TABLE story_assignment_log (...)` with index on `story_id`.
7. **Pre-flight before enforcing reporter `area_name`:** `SELECT id, name FROM users WHERE user_type='reporter' AND (area_name IS NULL OR TRIM(area_name)='');`. Expected zero rows. If zero → `ALTER TABLE users ALTER COLUMN area_name SET NOT NULL`. If any rows, abort, surface to admin, re-run after fixes.

**No story backfill** — all current stories are already approved per user. Historic `assigned_to` stays null. Escape hatch if anything misbehaves: `TRUNCATE story_assignment_log; UPDATE stories SET assigned_to=NULL, assigned_match_reason=NULL;`.

**Rollout order:**

1. Deploy DB migration via cloud-sql-proxy.
2. Deploy backend (`gcloud run deploy vrittant-api --source . --region asia-south1 --project vrittant-f5ef2 --allow-unauthenticated`).
3. Org admin opens user settings, assigns categories + regions to all current reviewers (one-time setup).
4. Deploy frontend (`cd reviewer-panel && npx vite build && npx firebase deploy --only hosting`).
5. Smoke: file a test story, confirm auto-assign + badge + reassign + audit log + filter.

## Testing

Per `superpowers:test-driven-development` — every behavior gets a failing test first.

**Backend unit (`pick_assignee()`):**
- Category match → least-loaded among matching reviewers.
- Tie on load → lowest user.id.
- "general" category skips step 1.
- Null category skips step 1.
- Region match works after normalize (case, whitespace, "district" suffix).
- Region match only fires when no category match.
- Overall fallback when no category and no region match.
- Deactivated reviewers excluded from all candidate pools.
- Empty-reviewer org → raises, story gets `assigned_to=null`.

**Backend integration:**
- `PATCH /assignee` writes log row with correct `from`, `to`, `assigned_by`, `reason='manual'`.
- `PATCH /assignee` rejects non-reviewer assignees.
- Reviewer deactivation redistributes all open stories and writes log rows with `reason='reviewer_deactivated'`.
- `GET /admin/stories?assigned_to=me` filters correctly.
- `PATCH /admin/users/{id}` rejects categories not in `OrgConfig.categories`.
- Reporter create/edit rejects empty `area_name`.

**Frontend:**
- Inline assignee dropdown calls the right endpoint and updates row optimistically.
- Filter URL (`?assigned_to=me|id|all`) persists across reload.

## Out of Scope (v1)

- In-app / email / push notifications on assignment.
- Bulk reassign UI.
- Rebalance-on-beat-change (admin edits a reviewer's beats → existing assignments stay put).
- Self-unassign (must always reassign to a specific person).
- Story backfill (no pending stories exist today).
- Closed enum of Odisha districts (regions stay free text with normalized matching).
