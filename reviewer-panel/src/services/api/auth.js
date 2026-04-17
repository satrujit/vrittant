/**
 * Auth domain: auth endpoints. Token storage helpers
 * (getAuthToken/setAuthToken/clearAuthToken) live in _internal.js
 * because apiFetch needs them at call time; they are re-exported here
 * so the public api surface (index.js) stays unchanged.
 */

import { apiFetch } from './_internal.js';

// ── Token management (re-exported from _internal to break the auth↔_internal cycle) ──
export { getAuthToken, setAuthToken, clearAuthToken } from './_internal.js';

// ── Auth API ──

export async function checkPhone(phone) {
  return apiFetch('/auth/check-phone', { method: 'POST', body: JSON.stringify({ phone }) });
}

export async function msg91Login(phone, accessToken) {
  return apiFetch('/auth/msg91-login', {
    method: 'POST',
    body: JSON.stringify({ phone, access_token: accessToken }),
  });
}

export async function requestOtp(phone) {
  return apiFetch('/auth/request-otp', { method: 'POST', body: JSON.stringify({ phone }) });
}

export async function verifyOtp(phone, otp, reqId = '') {
  return apiFetch('/auth/verify-otp', {
    method: 'POST',
    body: JSON.stringify({ phone, otp, req_id: reqId }),
  });
}

export async function resendOtp(phone, reqId = '') {
  return apiFetch('/auth/resend-otp', {
    method: 'POST',
    body: JSON.stringify({ phone, req_id: reqId }),
  });
}

export async function fetchCurrentUser() {
  return apiFetch('/auth/me');
}
