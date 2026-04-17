/**
 * Delta-aware SWR cache used by list endpoints.
 * Public surface: cachedGet, invalidateCache.
 * Everything else (the Map, _mergeDelta, _deltaUrl, STALE_MS, MAX_AGE_MS)
 * is module-private.
 */

import { apiFetch } from './_internal.js';

// ── Delta-Aware SWR Cache ──
// Shows cached data instantly on page revisit.
// Background revalidation fetches only changed items (delta) and merges.

const _cache = new Map(); // key → { data, timestamp, fetchedAt (ISO string) }
const STALE_MS = 30_000; // 30s — serve from cache, revalidate in background
const MAX_AGE_MS = 5 * 60_000; // 5 min — force refetch after this

/**
 * Merge a delta response into cached data.
 * Handles both list formats: { stories: [], total } and { reporters: [] }
 */
function _mergeDelta(cached, delta) {
  // Detect which list key is used
  const listKey = Object.keys(delta).find((k) => Array.isArray(delta[k]));
  if (!listKey || !cached[listKey]) return delta; // fallback to full replace

  const cachedList = [...cached[listKey]];
  const deltaList = delta[listKey];

  for (const item of deltaList) {
    if (item.is_deleted) {
      // Remove deleted items from cache
      const idx = cachedList.findIndex((c) => c.id === item.id);
      if (idx !== -1) cachedList.splice(idx, 1);
    } else {
      // Update existing or append new
      const idx = cachedList.findIndex((c) => c.id === item.id);
      if (idx !== -1) {
        cachedList[idx] = item;
      } else {
        cachedList.unshift(item); // new items at the top
      }
    }
  }

  const merged = { ...cached, [listKey]: cachedList };
  // Update total count if provided (reflects server-side count of all non-deleted items)
  if (delta.total != null) merged.total = delta.total;
  return merged;
}

/**
 * Build the delta URL by appending updated_since param.
 */
function _deltaUrl(path, isoTimestamp) {
  const sep = path.includes('?') ? '&' : '?';
  return `${path}${sep}updated_since=${encodeURIComponent(isoTimestamp)}`;
}

/**
 * Cached GET with delta support.
 * - If cache < STALE_MS old → return cache, no fetch
 * - If cache < MAX_AGE_MS old → return cache, delta-fetch in background & merge via onUpdate
 * - If cache expired or missing → full fetch
 *
 * @param {string} path - API path
 * @param {object} opts - { onUpdate?: (data) => void, delta?: boolean }
 *   delta: true enables delta fetching (default true for list endpoints)
 */
export async function cachedGet(path, opts = {}) {
  const cached = _cache.get(path);
  const now = Date.now();
  const useDelta = opts.delta !== false; // default true

  if (cached) {
    const age = now - cached.timestamp;
    if (age < STALE_MS) {
      return cached.data;
    }
    if (age < MAX_AGE_MS) {
      // Stale — return cached, revalidate in background
      const fetchUrl = useDelta && cached.fetchedAt
        ? _deltaUrl(path, cached.fetchedAt)
        : path;

      apiFetch(fetchUrl).then((data) => {
        const fetchedAt = new Date().toISOString();
        let merged;
        if (useDelta && cached.fetchedAt) {
          merged = _mergeDelta(cached.data, data);
        } else {
          merged = data;
        }
        _cache.set(path, { data: merged, timestamp: Date.now(), fetchedAt });
        if (opts.onUpdate) opts.onUpdate(merged);
      }).catch(() => {});
      return cached.data;
    }
  }

  // Expired or missing — full fetch
  const data = await apiFetch(path);
  const fetchedAt = new Date().toISOString();
  _cache.set(path, { data, timestamp: Date.now(), fetchedAt });
  return data;
}

/** Invalidate specific cache entries (call after mutations) */
export function invalidateCache(...pathPrefixes) {
  for (const key of _cache.keys()) {
    if (pathPrefixes.some((p) => key.startsWith(p))) {
      _cache.delete(key);
    }
  }
}
