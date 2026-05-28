/**
 * ThemeSwitcher — segmented button untuk pilih theme mode.
 *
 * Light / Dark / System (3 options).
 * Bisa dipakai standalone (compact) atau dalam settings page.
 */

import { BulbFilled, BulbOutlined, DesktopOutlined } from '@ant-design/icons';
import { Segmented, Tooltip } from 'antd';

import { type ThemeMode, usePreferencesStore } from '@/store/preferences';

interface Props {
  size?: 'small' | 'middle' | 'large';
  block?: boolean;
}

export function ThemeSwitcher({ size = 'middle', block = false }: Props) {
  const themeMode = usePreferencesStore((s) => s.themeMode);
  const setThemeMode = usePreferencesStore((s) => s.setThemeMode);

  return (
    <Tooltip title="Theme mode">
      <Segmented<ThemeMode>
        value={themeMode}
        onChange={(value) => setThemeMode(value)}
        size={size}
        block={block}
        options={[
          { label: 'Light', value: 'light', icon: <BulbOutlined aria-label="Light mode" /> },
          { label: 'Dark', value: 'dark', icon: <BulbFilled aria-label="Dark mode" /> },
          { label: 'System', value: 'system', icon: <DesktopOutlined aria-label="System theme" /> },
        ]}
        aria-label="Theme mode switcher"
      />
    </Tooltip>
  );
}
