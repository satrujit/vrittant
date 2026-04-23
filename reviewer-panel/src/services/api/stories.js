/**
 * Stories CRUD + semantic search + image upload + related lookups.
 * (deleteStory, createStory, uploadStoryImage, fetchRelatedStories
 * lived under unrelated comment-dividers in the legacy api.js — they are
 * stories, so they live here now.)
 */

import { apiGet, apiPost, apiPut, apiPatch, apiDelete } from '../http.js';
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
 * @param {object} params — { status, category, search, date_from, date_to, recent, offset, limit, assigned_to }
 *   assigned_to: a user id, or the literal string "me" to filter to the
 *   current user's assigned stories (resolved server-side from the token).
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
 * @param {string} status — "approved"|"rejected"|"published"|"flagged"|"layout_completed"|"submitted"
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

export async function adminDeleteStory(storyId) {
  const result = await apiDelete(`/admin/stories/${storyId}`);
  invalidateCache('/admin/stories');
  return result;
}

/**
 * Create a brand-new editor-authored story (the "+" button flow).
 *
 * The backend rejects empty payloads with 400 — the caller (Save button)
 * must already gate on having a headline or body, so an error here is
 * an unexpected programmer mistake rather than a routine outcome.
 *
 * Returns the freshly-created story (same shape as GET /admin/stories/{id}).
 */
export async function createStory(payload) {
  const result = await apiPost('/admin/stories', payload);
  invalidateCache('/admin/stories');
  return result;
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

/**
 * PATCH /admin/stories/:id/assignee
 * Reassign a story to a different user (or unassign with null).
 * @param {string|number} storyId
 * @param {string|number|null} assigneeId
 */
export async function reassignStory(storyId, assigneeId) {
  const result = await apiPatch(`/admin/stories/${storyId}/assignee`, {
    assignee_id: assigneeId,
  });
  invalidateCache('/admin/stories');
  return result;
}

/**
 * GET /admin/stories/:id/assignment-log
 * History of assignee changes for a story.
 */
export async function getAssignmentLog(storyId) {
  return apiGet(`/admin/stories/${storyId}/assignment-log`);
}

/**
 * GET /admin/stories/:id/comments
 * Editorial comments on a story (flat list, oldest first).
 */
export async function fetchStoryComments(storyId) {
  return apiGet(`/admin/stories/${storyId}/comments`);
}

/**
 * POST /admin/stories/:id/comments
 * Add a comment to a story.
 */
export async function postStoryComment(storyId, body) {
  return apiPost(`/admin/stories/${storyId}/comments`, { body });
}
