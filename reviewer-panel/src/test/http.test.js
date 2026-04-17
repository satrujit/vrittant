import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from '../services/http';

const API_BASE = 'http://api.test';

beforeEach(() => {
  vi.stubEnv('VITE_API_BASE', API_BASE);
  vi.stubGlobal('localStorage', {
    _s: {},
    getItem(k) { return this._s[k] ?? null; },
    setItem(k, v) { this._s[k] = String(v); },
    removeItem(k) { delete this._s[k]; },
  });
  globalThis.fetch = vi.fn();
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe('http wrapper', () => {
  it('apiGet sends GET with bearer token and returns JSON', async () => {
    localStorage.setItem('vr_token', 'tok');
    fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ x: 1 }) });
    const data = await apiGet('/foo');
    expect(data).toEqual({ x: 1 });
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/foo`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'Bearer tok' }),
      })
    );
  });

  it('apiPost sends JSON body', async () => {
    fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: true }) });
    await apiPost('/foo', { a: 1 });
    const [, opts] = fetch.mock.calls[0];
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ a: 1 });
  });

  it('throws ApiError with status on non-2xx', async () => {
    fetch.mockResolvedValue({
      ok: false, status: 422, statusText: 'Unprocessable',
      text: async () => '{"detail":"bad"}',
    });
    await expect(apiGet('/foo')).rejects.toMatchObject({
      name: 'ApiError', status: 422,
    });
  });

  it('returns null on 204', async () => {
    fetch.mockResolvedValue({ ok: true, status: 204 });
    expect(await apiDelete('/foo')).toBeNull();
  });

  it('omits Authorization header when no token is set', async () => {
    fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    await apiGet('/foo');
    const [, opts] = fetch.mock.calls[0];
    expect(opts.headers).not.toHaveProperty('Authorization');
  });

  it('clears token and throws ApiError(401, "Session expired") on 401', async () => {
    localStorage.setItem('vr_token', 'tok');
    fetch.mockResolvedValue({ ok: false, status: 401, statusText: 'Unauthorized' });
    await expect(apiGet('/foo')).rejects.toMatchObject({
      name: 'ApiError', status: 401, message: 'Session expired',
    });
    expect(localStorage.getItem('vr_token')).toBeNull();
  });

  it('apiPut sends PUT with JSON-stringified body', async () => {
    fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: true }) });
    await apiPut('/foo', { a: 1 });
    const [, opts] = fetch.mock.calls[0];
    expect(opts.method).toBe('PUT');
    expect(JSON.parse(opts.body)).toEqual({ a: 1 });
  });

  it('wraps fetch network failures as ApiError(0, "Network error: ...")', async () => {
    fetch.mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(apiGet('/foo')).rejects.toMatchObject({
      name: 'ApiError', status: 0, message: /Network error/,
    });
  });

  it('lifts FastAPI {detail: ...} into ApiError.message and keeps body parsed', async () => {
    const payload = { detail: 'phone already exists' };
    fetch.mockResolvedValue({
      ok: false,
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: { get: (k) => (k.toLowerCase() === 'content-type' ? 'application/json' : null) },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    await expect(apiPost('/x', {})).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      message: 'phone already exists',
      body: payload,
    });
  });

  it('falls back to "${status} ${statusText}" when response body is empty / non-JSON', async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => { throw new SyntaxError('Unexpected end of JSON input'); },
      text: async () => '',
    });
    await expect(apiGet('/foo')).rejects.toMatchObject({
      name: 'ApiError',
      status: 500,
      message: '500 Internal Server Error',
    });
  });
});
