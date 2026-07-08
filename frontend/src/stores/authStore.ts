// Auth store — user session and JWT token.

import { create } from "zustand";
import { api } from "../lib/api";

interface User { id: string; email: string; username: string }

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  loadFromStorage: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (email, password) => {
    const res = await api.login({ email, password });
    localStorage.setItem("token", res.access_token);
    const user = await api.getMe();
    set({ user, token: res.access_token, isAuthenticated: true });
  },

  register: async (email, username, password) => {
    const res = await api.register({ email, username, password });
    localStorage.setItem("token", res.access_token);
    const user = await api.getMe();
    set({ user, token: res.access_token, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem("token");
    set({ user: null, token: null, isAuthenticated: false });
  },

  loadFromStorage: () => {
    const token = localStorage.getItem("token");
    if (token) {
      api.getMe()
        .then((user) => set({ user, token, isAuthenticated: true, isLoading: false }))
        .catch(() => { localStorage.removeItem("token"); set({ isLoading: false }); });
    } else {
      set({ isLoading: false });
    }
  },
}));
