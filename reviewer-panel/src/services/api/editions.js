/**
 * Editions CRUD, edition-page CRUD, story-to-page mapping, and ZIP export.
 */

import { API_BASE, apiFetch, buildQuery } from './_internal.js';
import { getAuthToken } from './auth.js';

// ── Editions API ──

export async function fetchEditions(params = {}) {
  const query = buildQuery(params);
  return apiFetch(`/admin/editions${query}`);
}

export async function fetchEdition(id) {
  return apiFetch(`/admin/editions/${id}`);
}

export async function createEdition(data) {
  return apiFetch('/admin/editions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateEdition(id, data) {
  return apiFetch(`/admin/editions/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteEdition(id) {
  return apiFetch(`/admin/editions/${id}`, { method: 'DELETE' });
}

export async function addEditionPage(editionId, data) {
  return apiFetch(`/admin/editions/${editionId}/pages`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateEditionPage(editionId, pageId, data) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteEditionPage(editionId, pageId) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}`, {
    method: 'DELETE',
  });
}

export async function assignStoriesToPage(editionId, pageId, storyIds) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}/stories`, {
    method: 'PUT',
    body: JSON.stringify({ story_ids: storyIds }),
  });
}

export async function addStoryToPage(editionId, pageId, storyId) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}/stories/${storyId}`, {
    method: 'POST',
  });
}

export async function removeStoryFromPage(editionId, pageId, storyId) {
  return apiFetch(`/admin/editions/${editionId}/pages/${pageId}/stories/${storyId}`, {
    method: 'DELETE',
  });
}

export async function exportEditionZip(editionId) {
  const token = getAuthToken();
  const resp = await fetch(`${API_BASE}/admin/editions/${editionId}/export-zip`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Export failed: ${resp.status}`);
  }
  const blob = await resp.blob();
  const filename = resp.headers.get('Content-Disposition')?.match(/filename="(.+)"/)?.[1] || 'edition.zip';
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
