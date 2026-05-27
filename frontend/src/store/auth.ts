/**
 * Auth store — Zustand untuk client-side auth state.
 *
 * Sprint 1 (TSK-001): Simple state (user + token).
 * Sprint 1 (TSK-002): Tambah refresh token + auto-refresh logic.
 * Sprint 1 (TSK-005): Tambah session expiry + auto-logout.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { User } from '@/api/auth';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  setAuth: (user: User, accessToken: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      setAuth: (user, accessToken) =>
        set({ user, accessToken, isAuthenticated: true }),
      clearAuth: () => set({ user: null, accessToken: null, isAuthenticated: false }),
    }),
    {
      name: 'idea-auth-storage',
      // Hanya persist token + user, bukan loading states
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
