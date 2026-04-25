import {
  createElement,
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { authApi } from '../api/client';
import type { AuthState } from '../types';

type AuthContextValue = {
  auth: AuthState;
  login: (username: string, password: string) => Promise<unknown>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(() => {
    const token = localStorage.getItem('auth_token');
    return {
      token,
      user: null,
      isAuthenticated: false,
      isLoading: Boolean(token),
    };
  });

  useEffect(() => {
    let cancelled = false;
    const token = localStorage.getItem('auth_token');
    if (!token) {
      return undefined;
    }

    authApi
      .verify()
      .then((data) => {
        if (cancelled) return;
        if (data.valid) {
          setAuth({ token, user: data.user, isAuthenticated: true, isLoading: false });
          return;
        }
        localStorage.removeItem('auth_token');
        setAuth({ token: null, user: null, isAuthenticated: false, isLoading: false });
      })
      .catch(() => {
        if (cancelled) return;
        localStorage.removeItem('auth_token');
        setAuth({ token: null, user: null, isAuthenticated: false, isLoading: false });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = async (username: string, password: string) => {
    const data = await authApi.login(username, password);
    setAuth({
      token: data.token || data.access_token,
      user: data.user,
      isAuthenticated: true,
      isLoading: false,
    });
    return data;
  };

  const logout = () => {
    authApi.logout();
    setAuth({ token: null, user: null, isAuthenticated: false, isLoading: false });
  };

  return createElement(AuthContext.Provider, { value: { auth, login, logout } }, children);
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
