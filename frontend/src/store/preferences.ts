/**
 * User preferences store — theme, font size, motion preferences.
 *
 * Persist di localStorage (Zustand persist). Server-side preferences
 * akan ditambah di future TSK saat user profile API ada.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ThemeMode = 'light' | 'dark' | 'system';
export type FontSize = 'small' | 'medium' | 'large';

interface PreferencesState {
  themeMode: ThemeMode;
  fontSize: FontSize;
  reducedMotion: boolean;
  setThemeMode: (mode: ThemeMode) => void;
  setFontSize: (size: FontSize) => void;
  setReducedMotion: (enabled: boolean) => void;
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      themeMode: 'system',
      fontSize: 'medium',
      reducedMotion: false,
      setThemeMode: (themeMode) => set({ themeMode }),
      setFontSize: (fontSize) => set({ fontSize }),
      setReducedMotion: (reducedMotion) => set({ reducedMotion }),
    }),
    {
      name: 'idea-preferences',
    },
  ),
);

/**
 * Get effective theme — resolve 'system' ke 'light' atau 'dark'
 * berdasarkan OS preference.
 */
export function getEffectiveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'light' || mode === 'dark') return mode;
  // 'system' → check OS preference
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * Subscribe to OS theme changes (useful saat mode='system').
 * Returns cleanup function.
 */
export function watchSystemTheme(callback: (theme: 'light' | 'dark') => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const mql = window.matchMedia('(prefers-color-scheme: dark)');
  const handler = (e: MediaQueryListEvent) => callback(e.matches ? 'dark' : 'light');
  mql.addEventListener('change', handler);
  return () => mql.removeEventListener('change', handler);
}
