# Org Admin Role & Master Data Configuration

## Date: 2026-03-01

## Summary

Add an `org_admin` role that replaces the current `admin` user_type. Org admins are the top-level role per organization — they inherit all reviewer powers and gain user management, org settings, story deletion, and master data configuration capabilities.

## Role Structure

Three user types: `reporter`, `reviewer`, `org_admin`

| Capability | reporter | reviewer | org_admin |
|---|---|---|---|
| Own stories CRUD | Yes | — | — |
| View/approve/publish all org stories | — | Yes | Yes |
| Edit story revisions, editions | — | Yes | Yes |
| Delete any story | — | — | Yes |
| Add users to org | — | — | Yes |
| Disable/enable users | — | — | Yes |
| Assign user roles & entitlements | — | — | Yes |
| Update org details & logo | — | — | Yes |
| Configure master data | — | — | Yes |

## New Model: OrgConfig

Single config row per organization. JSON columns for flexible master data.

```
org_configs table:
  id              String (PK, UUID)
  organization_id String (FK → organizations.id, unique)
  categories      JSON   [{key, label, label_local, is_active}]
  publication_types JSON  [{key, label, is_active}]
  page_suggestions JSON   [{name, sort_order, is_active}]
  priority_levels JSON    [{key, label, label_local, is_active}]
  default_language String  "odia" | "english" | "hindi" etc.
  created_at      DateTime
  updated_at      DateTime
```

### Default seed values

**Categories:**
- politics / Politics / ରାଜନୀତି
- sports / Sports / କ୍ରୀଡ଼ା
- crime / Crime / ଅପରାଧ
- business / Business / ବ୍ୟବସାୟ
- entertainment / Entertainment / ମନୋରଞ୍ଜନ
- education / Education / ଶିକ୍ଷା
- health / Health / ସ୍ୱାସ୍ଥ୍ୟ
- technology / Technology / ପ୍ରଯୁକ୍ତି

**Publication types:** daily, weekend, evening, special

**Priority levels:** normal / Normal / ସାଧାରଣ, urgent / Urgent / ଜରୁରୀ, breaking / Breaking / ବ୍ରେକିଂ

**Page suggestions:** Front Page, Page 2, Page 3, Sports, Entertainment, State, National, International, Editorial, Classifieds

**Default language:** odia

## New API Endpoints

### User Management (require org_admin)

- `POST /admin/users` — Create user in org (name, phone, email, area_name, user_type)
- `PUT /admin/users/{id}` — Update user details (name, email, area_name, is_active)
- `PUT /admin/users/{id}/role` — Change user_type (reporter or reviewer only; cannot assign org_admin)
- `PUT /admin/users/{id}/entitlements` — Set entitlement page_keys

### Org Management (require org_admin)

- `PUT /admin/org` — Update org name, theme_color
- `PUT /admin/org/logo` — Upload new org logo (multipart file)

### Master Data Config (require org_admin)

- `GET /admin/config` — Get org's full config
- `PUT /admin/config` — Update config (partial updates supported)

### Story Deletion (require org_admin)

- `DELETE /admin/stories/{id}` — Hard delete any story in the org

### Public Config (authenticated, for app use)

- `GET /config/me` — Get current user's org config (categories, priorities, page suggestions, default language)

## Database Migration

1. Rename `user_type='admin'` → `'org_admin'` in users table
2. Create `org_configs` table
3. Seed default config for each existing organization

## What Stays Hardcoded

- Story statuses (draft/submitted/approved/rejected/published/in_progress) — workflow logic
- Edition statuses (draft/finalized/published) — workflow logic
- Media types (photo/video/audio/document) — file handling logic
- Entitlement page_keys — tied to actual admin UI pages
- User types (reporter/reviewer/org_admin) — code-level role checks

## Flutter App Changes

- Fetch categories, priorities, page suggestions from `/config/me` instead of hardcoded enums
- Cache config locally, refresh on app start
- Category enum replaced with dynamic list from API
- Priority enum replaced with dynamic list from API
