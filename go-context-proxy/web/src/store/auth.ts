import { create } from 'zustand';
import { authApi } from '../api/client';
import type { LoginRequest } from '../types';

interface AuthState {
  user: { id: number; username: string } | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (data: LoginRequest) => Promise<void>;
  logout: () => void;
  checkAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),

  login: async (data: LoginRequest) => {
    const response = await authApi.login(data);
    const { token, user } = response.data;
    
    localStorage.setItem('token', token);
    set({ user, token, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('token');
    set({ user: null, token: null, isAuthenticated: false });
    authApi.logout();
  },

  checkAuth: () => {
    const token = localStorage.getItem('token');
    set({ 
      token, 
      isAuthenticated: !!token 
    });
  },
}));
