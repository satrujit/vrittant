/**
 * Private shared infrastructure for the api/ modules.
 * Exports apiFetch (the legacy fetch wrapper), buildQuery, AVATAR_COLORS,
 * and API_BASE. The leading underscore in the filename signals that these
 * names are not part of the public services/api surface — only sibling
 * modules under services/api/ should import from here.
 *
 * Phase 2.1b will swap apiFetch usages for the apiGet/apiPost/apiPut/
 * apiDelete helpers in services/http.js, at which point this module
 * shrinks considerably.
 */

export const API_BASE = import.meta.env.VITE_API_BASE;

// ── Token management ──
// Lives here (not in auth.js) so apiFetch can use it without importing
// from auth.js — that import would form a load-order cycle. auth.js
// re-exports these three so the public api surface is unchanged.

export function getAuthToken() {
  return localStorage.getItem('vr_token');
}
export function setAuthToken(token) {
  localStorage.setItem('vr_token', token);
}
export function clearAuthToken() {
  localStorage.removeItem('vr_token');
}

/**
 * Generic fetch wrapper with error handling.
 * Returns parsed JSON on success, throws on failure.
 */
export async function apiFetch(path, options = {}) {
  const token = getAuthToken();
  const url = `${API_BASE}${path}`;
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
      ...options,
    });

    if (response.status === 401) {
      clearAuthToken();
      window.location.href = '/login';
      throw new Error('Session expired');
    }

    if (!response.ok) {
      const errorBody = await response.text().catch(() => '');
      throw new Error(
        `API error ${response.status}: ${response.statusText}${errorBody ? ` — ${errorBody}` : ''}`
      );
    }

    // 204 No Content has no body
    if (response.status === 204) return null;
    return await response.json();
  } catch (err) {
    if (err.message.startsWith('API error') || err.message === 'Session expired') {
      throw err;
    }
    throw new Error(`Network error: ${err.message}`);
  }
}

/**
 * Build a query string from a params object, omitting empty values.
 */
export function buildQuery(params) {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== ''
  );
  if (entries.length === 0) return '';
  return '?' + new URLSearchParams(entries).toString();
}

/**
 * Avatar palette used by getAvatarColor() in helpers.js.
 */
export const AVATAR_COLORS = [
  '#FA6C38', '#3D3B8E', '#14B8A6', '#6366F1',
  '#EC4899', '#F59E0B', '#10B981', '#EF4444',
  '#8B5CF6', '#0EA5E9', '#D97706', '#059669',
  '#E11D48', '#7C3AED', '#0891B2', '#CA8A04',
];
