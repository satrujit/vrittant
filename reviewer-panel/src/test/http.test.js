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
});
