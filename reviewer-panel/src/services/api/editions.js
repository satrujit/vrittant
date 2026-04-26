/**
 * Editions CRUD, edition-page CRUD, and story-to-page mapping.
 */

import { apiGet, apiPost, apiPut, apiDelete } from '../http.js';
import { buildQuery } from './_internal.js';
import { cachedGet, invalidateCache } from './cache.js';

// ── Editions API ──

// All edition reads share one SWR cache prefix so write paths only
// need to invalidate one string. Note `delta: false` — the editions
// endpoint doesn't yet support `updated_since`, so we revalidate by
// full-fetch (still cheap because the cache returns instantly while
// the background refetch runs).
const EDITIONS_CACHE_PREFIX = '/admin/editions';

export async function fetchEditions(params = {}, opts = {}) {
  const query = buildQuery(params);
  return cachedGet(`/admin/editions${query}`, { delta: false, ...opts });
}

export async function fetchEdition(id) {
  return apiGet(`/admin/editions/${id}`);
}

export async function createEdition(data) {
  const result = await apiPost('/admin/editions', data);
  invalidateCache(EDITIONS_CACHE_PREFIX);
  return result;
}

export async function updateEdition(id, data) {
  const result = await apiPut(`/admin/editions/${id}`, data);
  invalidateCache(EDITIONS_CACHE_PREFIX);
  return result;
}

export async function deleteEdition(id) {
  const result = await apiDelete(`/admin/editions/${id}`);
  invalidateCache(EDITIONS_CACHE_PREFIX);
  return result;
}

export async function addEditionPage(editionId, data) {
  const result = await apiPost(`/admin/editions/${editionId}/pages`, data);
  invalidateCache(EDITIONS_CACHE_PREFIX);
  return result;
}

export async function updateEditionPage(editionId, pageId, data) {
  const result = await apiPut(`/admin/editions/${editionId}/pages/${pageId}`, data);
  invalidateCache(EDITIONS_CACHE_PREFIX);
  return result;
}

export async function deleteEditionPage(editionId, pageId) {
  const result = await apiDelete(`/admin/editions/${editionId}/pages/${pageId}`);
  invalidateCache(EDITIONS_CACHE_PREFIX);
  return result;
}

export async function assignStoriesToPage(editionId, pageId, storyIds) {
  const result = await apiPut(`/admin/editions/${editionId}/pages/${pageId}/stories`, { story_ids: storyIds });
  invalidateCache(EDITIONS_CACHE_PREFIX);
  return result;
}

export async function addStoryToPage(editionId, pageId, storyId) {
  const result = await apiPost(`/admin/editions/${editionId}/pages/${pageId}/stories/${storyId}`);
  invalidateCache(EDITIONS_CACHE_PREFIX);
  return result;
}

export async function removeStoryFromPage(editionId, pageId, storyId) {
  const result = await apiDelete(`/admin/editions/${editionId}/pages/${pageId}/stories/${storyId}`);
  invalidateCache(EDITIONS_CACHE_PREFIX);
  return result;
}

// ── Multi-edition placement (matrix) ──

export async function getStoryPlacements(storyId) {
  return apiGet(`/admin/stories/${storyId}/placements`);
}

export async function setStoryPlacements(storyId, placements) {
  return apiPut(`/admin/stories/${storyId}/placements`, { placements });
}

/**
 * List editions for a single publication date with their pages eagerly
 * included. Used by the placement matrix to render one cell per edition
 * and a page picker per cell without N round-trips.
 */
export async function listTodaysEditions(date) {
  const query = buildQuery({ publication_date: date, limit: 100 });
  return apiGet(`/admin/editions${query}`);
}
