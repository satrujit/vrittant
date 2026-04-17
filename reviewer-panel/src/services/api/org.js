/**
 * Org admin: users, roles, entitlements, org metadata + logo + config.
 */

import { apiGet, apiPost, apiPut } from '../http.js';
import { API_BASE } from './_internal.js';
import { getAuthToken } from './auth.js';

// ── Org Admin API ──

export async function fetchOrgUsers({ includeInactive = false } = {}) {
  const params = includeInactive ? '?include_inactive=true' : '';
  return apiGet(`/admin/reporters${params}`);
}

export async function createUser(data) {
  return apiPost('/admin/users', data);
}

export async function updateUser(id, data) {
  return apiPut(`/admin/users/${id}`, data);
}

export async function updateUserRole(id, userType) {
  return apiPut(`/admin/users/${id}/role`, { user_type: userType });
}

export async function updateUserEntitlements(id, pageKeys) {
  return apiPut(`/admin/users/${id}/entitlements`, { page_keys: pageKeys });
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
