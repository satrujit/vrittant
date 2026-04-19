/**
 * Org admin: users, roles, entitlements, org metadata + logo + config.
 */

import { apiGet, apiPost, apiPut } from '../http.js';
import { API_BASE } from './_internal.js';
import { getAuthToken } from './auth.js';
import { invalidateCache } from './cache.js';

// ── Org Admin API ──

export async function fetchOrgUsers({ includeInactive = false } = {}) {
  const params = includeInactive ? '?include_inactive=true' : '';
  return apiGet(`/admin/reporters${params}`);
}

export async function createUser(data) {
  const result = await apiPost('/admin/users', data);
  // Sibling pages (ReportersPage, AllStoriesPage) read /admin/reporters via
  // cachedGet. Without invalidation, a stale cache (up to 5 min old) is
  // shown after a successful create, and the in-background delta merge can
  // miss rows whose updated_at falls inside the request-flight window.
  // Mirrors the pattern in stories.js after writes.
  invalidateCache('/admin/reporters');
  return result;
}

export async function updateUser(id, data) {
  const result = await apiPut(`/admin/users/${id}`, data);
  invalidateCache('/admin/reporters');
  return result;
}

/**
 * PUT /admin/users/:id/role
 * @param {string|number} id
 * @param {string} userType
 * @param {object} [extra] — optional { categories, regions } to update alongside the role.
 *   The reviewer-assignment work treats role + scope as a single edit; the
 *   backend accepts these fields on the role endpoint so the UI can save
 *   in one call.
 */
export async function updateUserRole(id, userType, extra = {}) {
  const body = { user_type: userType };
  if (extra.categories !== undefined) body.categories = extra.categories;
  if (extra.regions !== undefined) body.regions = extra.regions;
  const result = await apiPut(`/admin/users/${id}/role`, body);
  invalidateCache('/admin/reporters');
  return result;
}

/**
 * PUT /admin/users/:id/entitlements
 * @param {string|number} id
 * @param {string[]} pageKeys
 * @param {object} [extra] — optional { categories, regions } to update alongside entitlements.
 */
export async function updateUserEntitlements(id, pageKeys, extra = {}) {
  const body = { page_keys: pageKeys };
  if (extra.categories !== undefined) body.categories = extra.categories;
  if (extra.regions !== undefined) body.regions = extra.regions;
  const result = await apiPut(`/admin/users/${id}/entitlements`, body);
  invalidateCache('/admin/reporters');
  return result;
}

export async function updateOrg(data) {
  return apiPut('/admin/org', data);
}

export async function uploadOrgLogo(file) {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch(`${API_BASE}/admin/org/logo`, {
    method: 'PUT',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: formData,
  });
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
  return resp.json();
}

export async function fetchOrgConfig() {
  // /config/me is readable by any authed user; /admin/config requires
  // org_admin and 403s for reviewers/reporters — which silently emptied
  // dropdowns sourced from config (e.g. paper types in Create Edition).
  return apiGet('/config/me');
}

export async function updateOrgConfig(data) {
  return apiPut('/admin/config', data);
}
