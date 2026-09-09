import { useCallback, useEffect, useState } from 'react';
import { auth } from '../api/endpoints';
import { getToken, setToken } from '../api/client';

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) { setUser(null); setLoading(false); return null; }
    try {
      const u = await auth.me();
      setUser(u);
      return u;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = useCallback(async (username, password) => {
    const res = await auth.login(username, password);
    setToken(res.access_token);
    const u = await auth.me();
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(() => {
    setToken('');
    setUser(null);
    window.location.href = '/login';
  }, []);

  return { user, loading, login, logout, refresh };
}