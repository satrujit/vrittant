/**
 * Thin HTTP wrapper around fetch — one place for auth header, base URL,
 * 401 redirect, error shape. Use these from every API module.
 */

const TOKEN_KEY = 'vr_token';

export class ApiError extends Error {
  constructor(status, message, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

function authHeader() {
  const t = localStorage.getItem(TOKEN_KEY);
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function request(method, path, body) {
  const url = `${import.meta.env.VITE_API_BASE}${path}`;
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', ...authHeader() },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, `Network error: ${err.message}`, null);
  }

  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new ApiError(401, 'Session expired');
  }

  if (!res.ok) {
    let body;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => '');
    }
    const fallback = `${res.status} ${res.statusText}`;
    const message =
      body && typeof body === 'object'
        ? body.detail || body.message || fallback
        : fallback;
    throw new ApiError(res.status, message, body);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const apiGet    = (path)        => request('GET',    path);
export const apiPost   = (path, body)  => request('POST',   path, body);
export const apiPut    = (path, body)  => request('PUT',    path, body);
export const apiPatch  = (path, body)  => request('PATCH',  path, body);
export const apiDelete = (path)        => request('DELETE', path);
