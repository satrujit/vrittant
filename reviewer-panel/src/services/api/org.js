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

export async function updateUserRole(id, userType) {
  const result = await apiPut(`/admin/users/${id}/role`, { user_type: userType });
  invalidateCache('/admin/reporters');
  return result;
}

export async function updateUserEntitlements(id, pageKeys) {
  const result = await apiPut(`/admin/users/${id}/entitlements`, { page_keys: pageKeys });
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
  return apiGet('/admin/config');
}

export async function updateOrgConfig(data) {
  return apiPut('/admin/config', data);
}
