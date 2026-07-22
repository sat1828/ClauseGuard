import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api, setTokens, clearTokens, ApiError } from '../api/client';

const AuthContext = createContext(null);

function getStoredRefreshToken() {
  return localStorage.getItem('clauseguard_refresh_token');
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      setUser(null);
      clearTokens();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('clauseguard_access_token');
    if (token) {
      loadUser();
    } else {
      setLoading(false);
    }
  }, [loadUser]);

  const login = async (email, password) => {
    const res = await api.login(email, password);
    setTokens(res.access_token, res.refresh_token);
    await loadUser();
  };

  const register = async (email, password) => {
    const res = await api.register(email, password);
    setTokens(res.access_token, res.refresh_token);
    await loadUser();
  };

  const logout = async () => {
    const refreshToken = getStoredRefreshToken();
    // Best-effort: revoke server-side, but don't block the UI logout on it —
    // if the network is down, the person still expects to be logged out locally.
    if (refreshToken) {
      try {
        await api.logout(refreshToken);
      } catch {
        // ignore — local logout proceeds regardless
      }
    }
    clearTokens();
    setUser(null);
  };

  const logoutAllDevices = async () => {
    try {
      await api.logoutAll();
    } finally {
      clearTokens();
      setUser(null);
    }
  };

  const refreshUser = () => loadUser();

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, logoutAllDevices, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export { ApiError };
