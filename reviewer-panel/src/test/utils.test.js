import { describe, it, expect } from 'vitest';
import { formatDate } from '../utils/helpers';

describe('formatDate', () => {
  it('formats a valid date string', () => {
    const result = formatDate('2026-04-16T10:30:00Z');
    expect(result).toBeTruthy();
    expect(typeof result).toBe('string');
  });

  it('handles null/undefined gracefully', () => {
    const result = formatDate(null);
    // Should not throw
    expect(result !== undefined).toBe(true);
  });
});
