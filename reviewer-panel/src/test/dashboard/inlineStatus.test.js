import { describe, it, expect } from 'vitest';
import { STATUS_ORDER, cycleStatus, statusToken } from '../../components/dashboard/inlineStatus';

describe('inlineStatus helpers', () => {
  it('exports the canonical cycle order', () => {
    expect(STATUS_ORDER).toEqual([
      'submitted', 'in_progress', 'approved', 'rejected', 'flagged', 'published',
    ]);
  });

  it('cycleStatus moves to the next status', () => {
    expect(cycleStatus('submitted')).toBe('in_progress');
    expect(cycleStatus('in_progress')).toBe('approved');
    expect(cycleStatus('published')).toBe('submitted');
  });

  it('cycleStatus on unknown falls back to "submitted"', () => {
    expect(cycleStatus('garbage')).toBe('submitted');
  });

  it('statusToken returns semantic colour tokens', () => {
    expect(statusToken('approved').accent).toBe('emerald');
    expect(statusToken('rejected').accent).toBe('rose');
    expect(statusToken('submitted').accent).toBe('indigo');
  });
});
