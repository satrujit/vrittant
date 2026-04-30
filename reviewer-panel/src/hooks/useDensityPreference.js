/**
 * useDensityPreference — localStorage-backed dashboard row-density preference.
 *
 * Returns [density, setDensity] where density is one of the keys in DENSITIES
 * ('compact' | 'comfortable' | 'cozy'). Falls back to 'comfortable' when the
 * stored value is missing, unrecognised, or storage access throws (Safari
 * private mode, quota exceeded). Stays in sync across hook instances and
 * across tabs via the native `storage` event plus a custom
 * `density-preference-changed` event dispatched on every write.
 */
import { useEffect, useState, useCallback } from 'react';

export const DENSITIES = {
  compact:     { label: 'Compact',     rowHeight: 40 },
  comfortable: { label: 'Comfortable', rowHeight: 52 },
  cozy:        { label: 'Cozy',        rowHeight: 68 },
};

const STORAGE_KEY = 'vr_dashboard_density';
const EVENT = 'density-preference-changed';

function read() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return DENSITIES[stored] ? stored : 'comfortable';
  } catch {
    return 'comfortable';
  }
}

export function useDensityPreference() {
  const [value, setValue] = useState(read);

  useEffect(() => {
    const sync = () => setValue(read());
    window.addEventListener('storage', sync);
    window.addEventListener(EVENT, sync);
    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener(EVENT, sync);
    };
  }, []);

  const setDensity = useCallback((next) => {
    if (!DENSITIES[next]) return;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch { /* ignore storage failures */ }
    setValue(next);
    window.dispatchEvent(new Event(EVENT));
  }, []);

  return [value, setDensity];
}
