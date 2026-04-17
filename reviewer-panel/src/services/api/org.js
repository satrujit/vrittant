/**
 * Org admin: users, roles, entitlements, org metadata + logo + config.
 */

import { API_BASE, apiFetch } from './_internal.js';
import { getAuthToken } from './auth.js';

// ── Org Admin API ──

export async function fetchOrgUsers({ includeInactive = false } = {}) {
  const params = includeInactive ? '?include_inactive=true' : '';
  return apiFetch(`/admin/reporters${params}`);
}

export async function createUser(data) {
  return apiFetch('/admin/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateUser(id, data) {
  return apiFetch(`/admin/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function updateUserRole(id, userType) {
  return apiFetch(`/admin/users/${id}/role`, {
    method: 'PUT',
    body: JSON.stringify({ user_type: userType }),
  });
}

export async function updateUserEntitlements(id, pageKeys) {
  return apiFetch(`/admin/users/${id}/entitlements`, {
    method: 'PUT',
    body: JSON.stringify({ page_keys: pageKeys }),
  });
}

export async function updateOrg(data) {
  return apiFetch('/admin/org', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
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
  return apiFetch('/admin/config');
}

export async function updateOrgConfig(data) {
  return apiFetch('/admin/config', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}
