/**
 * Theme tokens sesuai design system knowledge.md sec.17.
 *
 * Color vars konsisten dengan mockup HTML di GUI html/.
 * Light + Dark variants. AntD theme bridge ke design tokens.
 */

import type { ThemeConfig } from 'antd';
import { theme as antdTheme } from 'antd';

import type { FontSize } from '@/store/preferences';

// ─── Color tokens dari knowledge.md sec.17 ────────────────────────

const LIGHT_COLORS = {
  blue: '#007AFF',
  green: '#30D158',
  orange: '#FF9F0A',
  red: '#FF453A',
  purple: '#BF5AF2',
  teal: '#32D2F2',

  // Backgrounds
  bg: '#F2F2F7',
  surface: '#FFFFFF',
  ink: '#0A0A0F',
  ink2: 'rgba(60,60,67,0.6)',  // text-sub
  ink3: 'rgba(60,60,67,0.38)', // text-muted
  border: 'rgba(0,0,0,0.07)',
};

const DARK_COLORS = {
  blue: '#0A84FF',
  green: '#32D74B',
  orange: '#FF9F0A',
  red: '#FF453A',
  purple: '#BF5AF2',
  teal: '#32D2F2',

  // Backgrounds (inverted)
  bg: '#0A0A0F',
  surface: '#1C1C1F',
  ink: '#F2F2F7',
  ink2: 'rgba(235,235,245,0.6)',
  ink3: 'rgba(235,235,245,0.38)',
  border: 'rgba(255,255,255,0.1)',
};

// ─── Font size scale ──────────────────────────────────────────────

const FONT_SIZE_MAP: Record<FontSize, number> = {
  small: 13,
  medium: 14,
  large: 16,
};

// ─── Build AntD ThemeConfig ───────────────────────────────────────

export function buildAntdTheme(
  effectiveTheme: 'light' | 'dark',
  fontSize: FontSize = 'medium',
  reducedMotion: boolean = false,
): ThemeConfig {
  const colors = effectiveTheme === 'dark' ? DARK_COLORS : LIGHT_COLORS;

  return {
    algorithm: effectiveTheme === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: colors.blue,
      colorSuccess: colors.green,
      colorWarning: colors.orange,
      colorError: colors.red,
      colorInfo: colors.teal,
      fontFamily: '"Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, sans-serif',
      fontSize: FONT_SIZE_MAP[fontSize],
      borderRadius: 8,
      // Motion — disable kalau reducedMotion enabled
      motionDurationMid: reducedMotion ? '0s' : '0.2s',
      motionDurationSlow: reducedMotion ? '0s' : '0.3s',
    },
    components: {
      Layout: {
        bodyBg: colors.bg,
        siderBg: colors.surface,
      },
      Card: {
        colorBgContainer: colors.surface,
      },
    },
  };
}

/**
 * Apply theme CSS variables ke document.documentElement.
 * Allows non-AntD components untuk reference --blue, --bg, dst.
 */
export function applyCssVariables(theme: 'light' | 'dark'): void {
  if (typeof document === 'undefined') return;
  const colors = theme === 'dark' ? DARK_COLORS : LIGHT_COLORS;
  const root = document.documentElement;
  root.setAttribute('data-theme', theme);
  for (const [key, value] of Object.entries(colors)) {
    root.style.setProperty(`--${key}`, value);
  }
}
