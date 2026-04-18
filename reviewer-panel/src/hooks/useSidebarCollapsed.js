import { useEffect, useState } from 'react';

/**
 * useSidebarCollapsed — manual collapse state for the global app sidebar.
 *
 * State is persisted in localStorage and broadcast across components via a
 * `storage` event (works cross-tab) plus a custom `sidebar-collapsed-changed`
 * event for same-tab sync (storage events don't fire in the originating tab).
 */
const KEY = 'vrittant.sidebar.collapsed';
const EVENT = 'sidebar-collapsed-changed';

function read() {
  try {
    return localStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
}

export function useSidebarCollapsed() {
  const [collapsed, setCollapsedState] = useState(read);

  useEffect(() => {
    const sync = () => setCollapsedState(read());
    window.addEventListener('storage', sync);
    window.addEventListener(EVENT, sync);
    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener(EVENT, sync);
    };
  }, []);

  const setCollapsed = (next) => {
    try {
      localStorage.setItem(KEY, next ? '1' : '0');
    } catch {
      // Ignore storage failures (private browsing, etc.) — local state still updates.
    }
    setCollapsedState(next);
    // Notify other consumers in this tab.
    window.dispatchEvent(new Event(EVENT));
  };

  return [collapsed, setCollapsed];
}
