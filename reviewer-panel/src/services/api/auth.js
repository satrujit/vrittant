/**
 * Auth domain: auth endpoints. Token storage helpers
 * (getAuthToken/setAuthToken/clearAuthToken) live in _internal.js
 * because FormData uploads + the STT WebSocket builder need them at
 * call time without going through http.js; they are re-exported here
 * so the public api surface (index.js) stays unchanged.
 */

import { apiGet, apiPost } from '../http.js';

// ── Token management (re-exported from _internal to break the auth↔_internal cycle) ──
export { getAuthToken, setAuthToken, clearAuthToken } from './_internal.js';

// ── Auth API ──

export async function checkPhone(phone) {
  return apiPost('/auth/check-phone', { phone });
}

export async function msg91Login(phone, accessToken) {
  return apiPost('/auth/msg91-login', { phone, access_token: accessToken });
}

export async function requestOtp(phone) {
  return apiPost('/auth/request-otp', { phone });
}

export async function verifyOtp(phone, otp, reqId = '') {
  return apiPost('/auth/verify-otp', { phone, otp, req_id: reqId });
}

export async function resendOtp(phone, reqId = '') {
  return apiPost('/auth/resend-otp', { phone, req_id: reqId });
}

export async function fetchCurrentUser() {
  return apiGet('/auth/me');
}
