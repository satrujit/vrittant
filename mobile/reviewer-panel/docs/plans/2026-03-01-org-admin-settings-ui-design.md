# Org Admin Settings UI — Design

## Date: 2026-03-01

## Summary

Add a Settings page to the reviewer-panel web app for org_admin users. Single page with three tabs: Users, Organization, Master Data. Accessible via a new sidebar nav item visible only to org_admin users.

## Sidebar

- New nav item: **Settings** (lucide `Settings` icon)
- Route: `/settings`
- Visibility: only when `user.user_type === "org_admin"`
- Position: last item before logout

## Page: `/settings`

Three tabs across the top: **Users** | **Organization** | **Master Data**

### Tab 1: Users

Table of all org users:

| Column | Content |
|--------|---------|
| Name | User name |
| Phone | Phone number |
| Role | reporter / reviewer badge |
| Area | Coverage area |
| Status | Active / Disabled badge |
| Actions | Edit, Disable/Enable, Entitlements |

**Add User** button (top right) opens a modal form:
- Name (required)
- Phone (required, +country code format)
- Email (optional)
- Area (optional)
- Role: reporter or reviewer (dropdown)

**Edit** action opens modal with: name, email, area fields.

**Disable/Enable** toggle — confirms before disabling.

**Entitlements** action opens modal with checkboxes:
- dashboard, stories, review, editions, reporters, social_export

**Role** dropdown inline or in edit modal: reporter / reviewer.

### Tab 2: Organization

Form layout:
- **Org name** — text input (current value pre-filled)
- **Theme color** — hex color input with preview swatch
- **Logo** — current logo preview + file upload button (PNG/JPG/WEBP/SVG, max 5MB)
- **Save** button

### Tab 3: Master Data

Accordion/collapsible sections:

**Categories** — Editable table:
- Columns: Key, Label, Local Label, Active (toggle)
- Add row button, remove row button per row

**Publication Types** — Editable table:
- Columns: Key, Label, Active (toggle)

**Page Suggestions** — Editable table:
- Columns: Name, Sort Order, Active (toggle)

**Priority Levels** — Editable table:
- Columns: Key, Label, Local Label, Active (toggle)

**Default Language** — Dropdown: odia / english / hindi

**Save** button at bottom.

## API Integration

New functions in `services/api.js`:
- `fetchOrgUsers()` → `GET /admin/reporters` (existing, returns all org users)
- `createUser(data)` → `POST /admin/users`
- `updateUser(id, data)` → `PUT /admin/users/{id}`
- `updateUserRole(id, data)` → `PUT /admin/users/{id}/role`
- `updateUserEntitlements(id, data)` → `PUT /admin/users/{id}/entitlements`
- `updateOrg(data)` → `PUT /admin/org`
- `uploadOrgLogo(file)` → `PUT /admin/org/logo`
- `fetchOrgConfig()` → `GET /admin/config`
- `updateOrgConfig(data)` → `PUT /admin/config`

## Access Control

- Sidebar item visibility: `user.user_type === "org_admin"`
- Route protection: redirect to `/` if not org_admin
- No new entitlement key needed — access is role-based

## Files to Create

- `src/pages/SettingsPage.jsx` + `SettingsPage.module.css`
- `src/components/settings/UsersTab.jsx`
- `src/components/settings/OrgTab.jsx`
- `src/components/settings/MasterDataTab.jsx`
- `src/components/settings/UserFormModal.jsx`
- `src/components/settings/EntitlementsModal.jsx`

## Files to Modify

- `src/App.jsx` — add `/settings` route
- `src/components/layout/Sidebar.jsx` — add Settings nav item with org_admin check
- `src/services/api.js` — add API functions
