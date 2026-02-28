# Story Revisions Design

## Problem

When a reviewer edits a story in the reviewer panel, the original reporter submission is overwritten. The reporter's original content is lost, making it impossible to compare what was submitted vs what was published.

## Decision

Introduce a `story_revisions` table that stores the editor's version separately. The `stories` table remains immutable after submission — it always reflects the reporter's original content.

## Data Model

### New table: `story_revisions`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | UUID | PK, auto-generated | |
| `story_id` | String | FK -> stories.id, UNIQUE | One revision per story |
| `editor_id` | String | FK -> users.id | Who made the edit |
| `headline` | String | NOT NULL | Edited headline |
| `paragraphs` | JSON | NOT NULL | Edited paragraphs (same schema as stories.paragraphs) |
| `created_at` | DateTime | auto | When first saved |
| `updated_at` | DateTime | auto | Last save time |

UNIQUE constraint on `story_id` ensures exactly 0 or 1 revision per story. Saves after the first do an UPDATE, not INSERT.

### `stories` table

No changes. Stays immutable after reporter submits.

## API Changes

### `PUT /admin/stories/{story_id}` (Content Update)

**Before:** Overwrites `stories.headline` and `stories.paragraphs`.

**After:** Upserts a `story_revisions` row:
- If no revision exists for this story: INSERT with editor_id from JWT
- If revision exists: UPDATE headline, paragraphs, updated_at

Request body unchanged: `{ headline, category, paragraphs }`

### `GET /admin/stories/{story_id}` (Fetch Story)

**Before:** Returns story fields only.

**After:** Include a `revision` field in the response:
```json
{
  "id": "...",
  "headline": "Original headline",
  "paragraphs": [...],
  "revision": {
    "id": "...",
    "editor_id": "...",
    "headline": "Edited headline",
    "paragraphs": [...],
    "updated_at": "..."
  }
}
```

`revision` is `null` if no editor revision exists.

### `GET /admin/stories` (List Stories)

Include a boolean `has_revision` flag so the list view can indicate which stories have been edited.

## Frontend Changes

### ReviewPage.jsx

- **On load:** If `story.revision` exists, populate the TipTap editor with `revision.headline` and `revision.paragraphs`. Otherwise show original content.
- **Save Draft:** Calls same `updateStory()` function. Backend handles writing to revisions table.
- **Visual indicator:** Show a subtle badge or label when viewing edited content vs original.
- **Original content:** Remains visible in the properties panel (read-only).

### Stories List

- Show an "Edited" badge on stories that have a revision.

## Publish/Export Flow

When a story is approved and exported (InDesign, social media), always read from `story_revisions`. If no revision exists, the story cannot be published (editor must review and save first, or the original can be approved as-is by creating a revision that copies the original).

## Visibility Rules

- **Reporter:** Sees only their original submitted content. No visibility into editor revisions.
- **Reviewer/Editor:** Sees both original (in properties panel) and edited version (in editor). Can toggle between them.
- **Publish pipeline:** Uses the edited + approved version only.
