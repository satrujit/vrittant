/**
 * Auth domain: token storage + auth endpoints.
 * The token getters/setters live here because apiFetch (in _internal.js)
 * needs to read and clear the token, but they are also part of the public
 * api surface re-exported from index.js.
 */

import { apiFetch } from './_internal.js';

// ── Token management ──

export function getAuthToken() {
  return localStorage.getItem('vr_token');
}
export function setAuthToken(token) {
  localStorage.setItem('vr_token', token);
}
export function clearAuthToken() {
  localStorage.removeItem('vr_token');
}

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
