/**
 * Reporter list + per-reporter story feed.
 */

import { apiGet } from '../http.js';
import { buildQuery } from './_internal.js';
import { cachedGet } from './cache.js';

/**
 * GET /admin/reporters
 * Returns: { reporters: [...] }
 */
export async function fetchReporters({ includeInactive = false, ...opts } = {}) {
  const params = includeInactive ? '?include_inactive=true' : '';
  return cachedGet(`/admin/reporters${params}`, opts);
}

/**
 * GET /admin/reporters/:id/stories
 * @param {string|number} reporterId
 * @param {object} params — same filters as fetchStories
 * Returns: { stories: [...], total: N }
 */
export async function fetchReporterStories(reporterId, params = {}) {
  const query = buildQuery(params);
  return apiGet(`/admin/reporters/${reporterId}/stories${query}`);
}
