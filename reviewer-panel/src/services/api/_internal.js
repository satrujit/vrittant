/**
 * Private shared infrastructure for the api/ modules.
 * Exports API_BASE, buildQuery, AVATAR_COLORS, and the three localStorage
 * token helpers. The leading underscore in the filename signals that these
 * names are not part of the public services/api surface — only sibling
 * modules under services/api/ should import from here.
 *
 * After Phase 2.1b, the legacy apiFetch wrapper is gone — every api/<domain>.js
 * module now goes through apiGet/apiPost/apiPut/apiDelete in services/http.js.
 * The token helpers stay here because the FormData uploads (uploadOrgLogo,
 * uploadStoryImage), the blob download (exportEditionZip), and the STT
 * WebSocket URL builder all need raw fetch + Authorization header at call
 * time — those shapes don't fit the JSON wrapper.
 */

export const API_BASE = import.meta.env.VITE_API_BASE;

// ── Token management ──
// auth.js re-exports these three so the public api surface is unchanged.

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
