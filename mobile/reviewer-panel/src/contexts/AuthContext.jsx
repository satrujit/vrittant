import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { fetchCurrentUser, fetchOrgConfig, setAuthToken, clearAuthToken, getAuthToken } from '../services/api';
import { auth } from '../services/firebase';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      Promise.all([
        fetchCurrentUser().catch((err) => {
          // Only clear token on explicit 401 (session expired), NOT on network/CORS errors
          if (err.message === 'Session expired') { clearAuthToken(); }
          return null;
        }),
        fetchOrgConfig().catch(() => null),
      ]).then(([u, c]) => {
        if (!u) { setUser(null); } else { setUser(u); }
        setConfig(c);
      }).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback((token) => {
    setAuthToken(token);
    return fetchCurrentUser().then((u) => {
      setUser(u);
      fetchOrgConfig().then(setConfig).catch(() => {});
      return u;
    });
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    setUser(null);
    try { auth.signOut(); } catch {}
  }, []);

  const refreshUser = useCallback(async () => {
    const data = await fetchCurrentUser();
    setUser(data);
    return data;
  }, []);

  const refreshConfig = useCallback(async () => {
    const data = await fetchOrgConfig();
    setConfig(data);
    return data;
  }, []);

  const hasEntitlement = useCallback(
    (pageKey) => {
      if (!user?.entitlements) return false;
      return user.entitlements.some((e) => e.page_key === pageKey);
    },
    [user]
  );

  return (
    <AuthContext.Provider value={{ user, config, loading, login, logout, hasEntitlement, refreshUser, refreshConfig }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
