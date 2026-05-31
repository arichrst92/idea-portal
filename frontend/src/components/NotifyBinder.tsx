/**
 * NotifyBinder — bridge AntD `App.useApp()` ke global proxies di `@/lib/notify`.
 *
 * Mount sekali di app root (dalam <AntApp>) supaya semua `import { message } from '@/lib/notify'`
 * pick up theme context dengan benar (no more static-message warnings).
 */

import { App as AntApp } from 'antd';
import { useEffect } from 'react';

import { bindNotifyApi } from '@/lib/notify';

export function NotifyBinder() {
  const { message, modal, notification } = AntApp.useApp();
  useEffect(() => {
    bindNotifyApi({ message, modal, notification });
  }, [message, modal, notification]);
  return null;
}
