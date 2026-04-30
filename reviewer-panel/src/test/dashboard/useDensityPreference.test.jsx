import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDensityPreference, DENSITIES } from '../../hooks/useDensityPreference';

describe('useDensityPreference', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('defaults to "comfortable"', () => {
    const { result } = renderHook(() => useDensityPreference());
    expect(result.current[0]).toBe('comfortable');
  });

  it('reads persisted value from localStorage', () => {
    localStorage.setItem('vr_dashboard_density', 'compact');
    const { result } = renderHook(() => useDensityPreference());
    expect(result.current[0]).toBe('compact');
  });

  it('writes new value to localStorage', () => {
    const { result } = renderHook(() => useDensityPreference());
    act(() => result.current[1]('cozy'));
    expect(result.current[0]).toBe('cozy');
    expect(localStorage.getItem('vr_dashboard_density')).toBe('cozy');
  });

  it('rejects unknown values silently and keeps current', () => {
    const { result } = renderHook(() => useDensityPreference());
    act(() => result.current[1]('huge'));
    expect(result.current[0]).toBe('comfortable');
  });

  it('falls back to "comfortable" when localStorage holds an unrecognised value at mount', () => {
    localStorage.setItem('vr_dashboard_density', 'huge');
    const { result } = renderHook(() => useDensityPreference());
    expect(result.current[0]).toBe('comfortable');
  });

  it('exports a DENSITIES record with row-height pixels', () => {
    expect(DENSITIES.compact.rowHeight).toBe(40);
    expect(DENSITIES.comfortable.rowHeight).toBe(52);
    expect(DENSITIES.cozy.rowHeight).toBe(68);
  });
});
