/**
 * Regression test for Bug 2 (2026-04-18 batch):
 * Newly added users not visible in admin Settings → Users tab.
 *
 * The original code path was:
 *   ReportersPage / AllStoriesPage → cachedGet('/admin/reporters')
 *     → populates module-level _cache
 *   UsersTab.handleCreate → createUser() → loadUsers() (NOT awaited)
 *
 * createUser did not invalidate the /admin/reporters cache, so sibling
 * pages kept showing stale lists, and loadUsers ran in parallel with
 * the modal close — making the new row appear unreliably.
 *
 * The fix:
 *   1. Mutation helpers in services/api/org.js call invalidateCache(...)
 *      after a successful write.
 *   2. UsersTab handlers await loadUsers() before completing, so the
 *      modal's `await onSubmit(...)` waits until the table is refreshed.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the http wrapper so we can drive request behaviour from the test.
vi.mock('../services/http.js', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

import { apiGet, apiPost, apiPut } from '../services/http.js';
import { cachedGet, invalidateCache } from '../services/api/cache.js';
import { createUser, updateUser, updateUserRole, updateUserEntitlements } from '../services/api/org.js';

beforeEach(() => {
  apiGet.mockReset();
  apiPost.mockReset();
  apiPut.mockReset();
  // Drain any cache state left over from previous tests.
  invalidateCache('/admin/reporters', '/admin/stories');
});

describe('org user mutations invalidate /admin/reporters cache', () => {
  async function primeCache() {
    apiGet.mockResolvedValueOnce({ reporters: [{ id: 'old', name: 'Old User' }] });
    const first = await cachedGet('/admin/reporters');
    expect(first.reporters).toHaveLength(1);
    expect(apiGet).toHaveBeenCalledTimes(1);
  }

  it('createUser clears the reporters cache so the next read refetches', async () => {
    await primeCache();

    apiPost.mockResolvedValueOnce({ id: 'new', name: 'New User' });
    await createUser({ name: 'New User', phone: '+919999999999' });

    // Cache must now be empty for /admin/reporters → cachedGet must fetch again.
    apiGet.mockResolvedValueOnce({
      reporters: [
        { id: 'old', name: 'Old User' },
        { id: 'new', name: 'New User' },
      ],
    });
    const second = await cachedGet('/admin/reporters');
    expect(apiGet).toHaveBeenCalledTimes(2); // <-- bug repro: stayed at 1 before fix
    expect(second.reporters.map((r) => r.id)).toContain('new');
  });

  it('updateUser clears the reporters cache', async () => {
    await primeCache();
    apiPut.mockResolvedValueOnce({ id: 'old', name: 'Renamed' });
    await updateUser('old', { name: 'Renamed' });

    apiGet.mockResolvedValueOnce({ reporters: [{ id: 'old', name: 'Renamed' }] });
    await cachedGet('/admin/reporters');
    expect(apiGet).toHaveBeenCalledTimes(2);
  });

  it('updateUserRole clears the reporters cache', async () => {
    await primeCache();
    apiPut.mockResolvedValueOnce({ id: 'old', user_type: 'reviewer' });
    await updateUserRole('old', 'reviewer');

    apiGet.mockResolvedValueOnce({ reporters: [] });
    await cachedGet('/admin/reporters');
    expect(apiGet).toHaveBeenCalledTimes(2);
  });

  it('updateUserEntitlements clears the reporters cache', async () => {
    await primeCache();
    apiPut.mockResolvedValueOnce({ id: 'old', entitlements: ['stories'] });
    await updateUserEntitlements('old', ['stories']);

    apiGet.mockResolvedValueOnce({ reporters: [] });
    await cachedGet('/admin/reporters');
    expect(apiGet).toHaveBeenCalledTimes(2);
  });
});

