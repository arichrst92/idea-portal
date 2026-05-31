/**
 * Notify helper — bridges static `message` / `Modal` imports ke AntD `App.useApp()`
 * context, supaya dynamic theme + token (warna, fontFamily, dst) ke-pickup.
 *
 * Usage pattern:
 *   import { message, modal, notification } from '@/lib/notify';
 *   message.success('OK');
 *   modal.confirm({ title: '...', onOk: () => {} });
 *
 * Binding terjadi sekali di runtime via NotifyBinder (rendered di AppRoutes top).
 * Sebelum binder render, calls jadi no-op (silent) — aman karena root mount instan.
 */

import type { MessageInstance } from 'antd/es/message/interface';
import type { NotificationInstance } from 'antd/es/notification/interface';
import type { HookAPI as ModalHookAPI } from 'antd/es/modal/useModal';

let _message: MessageInstance | null = null;
let _modal: ModalHookAPI | null = null;
let _notification: NotificationInstance | null = null;

export function bindNotifyApi(api: {
  message: MessageInstance;
  modal: ModalHookAPI;
  notification: NotificationInstance;
}): void {
  _message = api.message;
  _modal = api.modal;
  _notification = api.notification;
}

type MsgArgs = Parameters<MessageInstance['success']>;

export const message = {
  success: (...args: MsgArgs) => _message?.success(...args),
  error: (...args: MsgArgs) => _message?.error(...args),
  warning: (...args: MsgArgs) => _message?.warning(...args),
  info: (...args: MsgArgs) => _message?.info(...args),
  loading: (...args: MsgArgs) => _message?.loading(...args),
  open: ((...args: any[]) => _message?.open?.(...(args as Parameters<MessageInstance['open']>))) as MessageInstance['open'],
  destroy: (key?: string | number) =>
    key !== undefined ? _message?.destroy(key) : _message?.destroy(),
};

/**
 * Imperative Modal API (lowercase to mirror App.useApp().modal pattern).
 * Use this for `modal.confirm({...})` etc. — does NOT collide with JSX `<Modal>`
 * component (which stays imported from antd).
 */
export const modal = {
  confirm: (cfg: Parameters<ModalHookAPI['confirm']>[0]) => _modal?.confirm(cfg),
  info: (cfg: Parameters<ModalHookAPI['info']>[0]) => _modal?.info(cfg),
  success: (cfg: Parameters<ModalHookAPI['success']>[0]) => _modal?.success(cfg),
  error: (cfg: Parameters<ModalHookAPI['error']>[0]) => _modal?.error(cfg),
  warning: (cfg: Parameters<ModalHookAPI['warning']>[0]) => _modal?.warning(cfg),
};

/** @deprecated alias kept for back-compat. Prefer lowercase `modal`. */
export const Modal = modal;

export const notification = {
  success: (cfg: Parameters<NotificationInstance['success']>[0]) =>
    _notification?.success(cfg),
  error: (cfg: Parameters<NotificationInstance['error']>[0]) =>
    _notification?.error(cfg),
  warning: (cfg: Parameters<NotificationInstance['warning']>[0]) =>
    _notification?.warning(cfg),
  info: (cfg: Parameters<NotificationInstance['info']>[0]) =>
    _notification?.info(cfg),
  open: (cfg: Parameters<NotificationInstance['open']>[0]) =>
    _notification?.open(cfg),
  destroy: (key?: string) =>
    key !== undefined ? _notification?.destroy(key) : _notification?.destroy(),
};
