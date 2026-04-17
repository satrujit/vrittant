/**
 * Editions CRUD, edition-page CRUD, story-to-page mapping, and ZIP export.
 */

import { apiGet, apiPost, apiPut, apiDelete } from '../http.js';
import { API_BASE, buildQuery } from './_internal.js';
import { getAuthToken } from './auth.js';

// ── Editions API ──

export async function fetchEditions(params = {}) {
  const query = buildQuery(params);
  return apiGet(`/admin/editions${query}`);
}

export async function fetchEdition(id) {
  return apiGet(`/admin/editions/${id}`);
}

export async function createEdition(data) {
  return apiPost('/admin/editions', data);
}

export async function updateEdition(id, data) {
  return apiPut(`/admin/editions/${id}`, data);
}

export async function deleteEdition(id) {
  return apiDelete(`/admin/editions/${id}`);
}

export async function addEditionPage(editionId, data) {
  return apiPost(`/admin/editions/${editionId}/pages`, data);
}

export async function updateEditionPage(editionId, pageId, data) {
  return apiPut(`/admin/editions/${editionId}/pages/${pageId}`, data);
}

export async function deleteEditionPage(editionId, pageId) {
  return apiDelete(`/admin/editions/${editionId}/pages/${pageId}`);
}

export async function assignStoriesToPage(editionId, pageId, storyIds) {
  return apiPut(`/admin/editions/${editionId}/pages/${pageId}/stories`, { story_ids: storyIds });
}

export async function addStoryToPage(editionId, pageId, storyId) {
  return apiPost(`/admin/editions/${editionId}/pages/${pageId}/stories/${storyId}`);
}

export async function removeStoryFromPage(editionId, pageId, storyId) {
  return apiDelete(`/admin/editions/${editionId}/pages/${pageId}/stories/${storyId}`);
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
