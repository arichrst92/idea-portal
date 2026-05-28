/**
 * ThemeProvider — wrap aplikasi dengan AntD ConfigProvider + sync OS theme changes.
 *
 * Replaces statik ConfigProvider di main.tsx.
 * Listen ke preferences store + OS theme media query.
 */

import { App as AntApp, ConfigProvider } from 'antd';
import idID from 'antd/locale/id_ID';
import { useEffect, useMemo } from 'react';

import { applyCssVariables, buildAntdTheme } from '@/lib/theme';
import { getEffectiveTheme, usePreferencesStore, watchSystemTheme } from '@/store/preferences';

interface Props {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: Props) {
  const themeMode = usePreferencesStore((s) => s.themeMode);
  const fontSize = usePreferencesStore((s) => s.fontSize);
  const reducedMotion = usePreferencesStore((s) => s.reducedMotion);

  // Resolve 'system' → 'light' atau 'dark'
  const effectiveTheme = useMemo(() => getEffectiveTheme(themeMode), [themeMode]);

  // Apply CSS variables ke document
  useEffect(() => {
    applyCssVariables(effectiveTheme);
  }, [effectiveTheme]);

  // Watch OS theme changes saat mode='system'
  useEffect(() => {
    if (themeMode !== 'system') return;
    const unsubscribe = watchSystemTheme((newTheme) => {
      applyCssVariables(newTheme);
    });
    return unsubscribe;
  }, [themeMode]);

  // Set body background sesuai theme
  useEffect(() => {
    const body = document.body;
    body.style.background = effectiveTheme === 'dark' ? '#0A0A0F' : '#F2F2F7';
    body.style.color = effectiveTheme === 'dark' ? '#F2F2F7' : '#0A0A0F';
  }, [effectiveTheme]);

  const antdConfig = useMemo(
    () => buildAntdTheme(effectiveTheme, fontSize, reducedMotion),
    [effectiveTheme, fontSize, reducedMotion],
  );

  return (
    <ConfigProvider theme={antdConfig} locale={idID}>
      <AntApp>{children}</AntApp>
    </ConfigProvider>
  );
}
