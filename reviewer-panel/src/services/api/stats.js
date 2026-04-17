/**
 * Admin dashboard stats — totals, heatmap, leaderboard.
 */

import { apiFetch } from './_internal.js';
import { cachedGet } from './cache.js';

/**
 * GET /admin/stats
 * Returns: { pending_review, reviewed_today, avg_ai_accuracy, total_published, total_stories, total_reporters }
 */
export async function fetchStats(opts = {}) {
  return cachedGet('/admin/stats', opts);
}

export async function fetchActivityHeatmap(days = 365, reporterId = null) {
  let url = `/admin/activity-heatmap?days=${days}`;
  if (reporterId) url += `&reporter_id=${reporterId}`;
  return apiFetch(url);
}

export async function fetchLeaderboard(period = 'month', opts = {}) {
  return cachedGet(`/admin/leaderboard?period=${period}`, opts);
}
