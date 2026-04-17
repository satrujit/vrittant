/**
 * Stories CRUD + semantic search + image upload + related lookups.
 * (deleteStory, createBlankStory, uploadStoryImage, fetchRelatedStories
 * lived under unrelated comment-dividers in the legacy api.js — they are
 * stories, so they live here now.)
 */

import { apiGet, apiPost, apiPut, apiDelete } from '../http.js';
import { API_BASE, buildQuery } from './_internal.js';
import { cachedGet, invalidateCache } from './cache.js';
import { getAuthToken } from './auth.js';

export async function semanticSearchStories(params = {}) {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set('q', params.q);
  if (params.offset != null) searchParams.set('offset', String(params.offset));
  if (params.limit != null) searchParams.set('limit', String(params.limit));
  return apiGet(`/admin/stories/semantic-search?${searchParams.toString()}`);
}

/**
 * GET /admin/stories
 * @param {object} params — { status, category, search, date_from, date_to, recent, offset, limit }
 * Returns: { stories: [...], total: N }
 */
export async function fetchStories(params = {}, opts = {}) {
  const query = buildQuery(params);
  return cachedGet(`/admin/stories${query}`, opts);
}

/**
 * GET /admin/stories/:id
 * Returns a single story object with nested reporter info.
 */
export async function fetchStory(id) {
  return apiGet(`/admin/stories/${id}`);
}

/**
 * PUT /admin/stories/:id/status
 * @param {string|number} id
 * @param {string} status — "approved"|"rejected"|"published"|"in_progress"
 * @param {string} reason — optional reason for rejection or changes
 */
export async function updateStoryStatus(id, status, reason = '') {
  const result = await apiPut(`/admin/stories/${id}/status`, { status, reason });
  invalidateCache('/admin/stories', '/admin/stats', '/admin/leaderboard', '/admin/reporters');
  return result;
}

/**
 * PUT /admin/stories/:id
 * @param {string|number} id
 * @param {object} data — { headline, category, paragraphs }
 */
export async function updateStory(id, data) {
  const result = await apiPut(`/admin/stories/${id}`, data);
  invalidateCache('/admin/stories');
  return result;
}

export async function deleteStory(id) {
  return apiDelete(`/admin/stories/${id}`);
}

export async function createBlankStory() {
  return apiPost('/admin/stories/create-blank');
}

export async function uploadStoryImage(storyId, file) {
  const token = getAuthToken();
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch(`${API_BASE}/admin/stories/${storyId}/upload-image`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: formData,
  });
  if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`);
  return resp.json();
}

export async function fetchRelatedStories(storyId) {
  return apiGet(`/admin/stories/${storyId}/related`);
}
