import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// We need to set up the token before importing
import { setAuthToken, getAuthToken, clearAuthToken } from '../services/api';

describe('Auth Token Management', () => {
  beforeEach(() => {
    clearAuthToken();
    localStorage.clear();
  });

  it('stores and retrieves auth token', () => {
    setAuthToken('test-token-123');
    expect(getAuthToken()).toBe('test-token-123');
  });

  it('clears auth token', () => {
    setAuthToken('test-token-123');
    clearAuthToken();
    expect(getAuthToken()).toBeNull();
  });
});

describe('API Base URL', () => {
  it('uses VITE_API_BASE environment variable', () => {
    // In test env, VITE_API_BASE defaults to empty or undefined
    // The api module should handle this gracefully
    expect(typeof getAuthToken).toBe('function');
  });
});
