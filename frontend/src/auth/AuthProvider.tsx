import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { api, clearCsrfToken, loadCsrfToken } from '../api/client';
import type { User } from './types';

type AuthState = 'loading' | 'authenticated' | 'unauthenticated' | 'error';
type AuthContextValue = { user: User | null; state: AuthState; refresh: () => Promise<void>; logout: () => Promise<void> };
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [state, setState] = useState<AuthState>('loading');
  const refresh = async () => {
    try { const response = await api.get<User>('/auth/me'); setUser(response.data); setState('authenticated'); }
    catch (error: any) { setUser(null); setState(error?.response?.status === 401 ? 'unauthenticated' : 'error'); }
  };
  useEffect(() => { void refresh(); }, []);
  const logout = async () => { try { await loadCsrfToken(); await api.post('/auth/logout'); } finally { clearCsrfToken(); setUser(null); setState('unauthenticated'); } };
  const value = useMemo(() => ({ user, state, refresh, logout }), [user, state]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('useAuth must be used inside AuthProvider'); return value; }
