import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api, User, clearToken, setToken } from '../api/apiClient';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount, check if a stored token is still valid
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      api.getMe()
        .then(u => setUser(u))
        .catch(() => { clearToken(); })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    try {
      const result = await api.login(email, password);
      setUser(result.user);
      return { success: true };
    } catch (err: any) {
      return { success: false, error: err.message || 'Invalid email or password.' };
    }
  };

  const logout = () => {
    api.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
