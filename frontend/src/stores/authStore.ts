// Auth store — Google OAuth + HttpOnly cookie.

import { create } from "zustand";
import { api } from "../lib/api";

interface User { id: number; email: string; username: string }

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginWithCode: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  loginWithCode: async (code) => {
    await api.googleAuth(code);
    const user = await api.getMe();
    set({ user, isAuthenticated: true });
  },

  logout: async () => {
    await api.logout();                       // clears cookie
    set({ user: null, isAuthenticated: false });
  },

  checkSession: async () => {
    try {
      const user = await api.getMe();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },
}));
