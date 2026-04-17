/**
 * Editions CRUD, edition-page CRUD, and story-to-page mapping.
 */

import { apiGet, apiPost, apiPut, apiDelete } from '../http.js';
import { buildQuery } from './_internal.js';

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
