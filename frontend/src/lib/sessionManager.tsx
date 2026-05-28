/**
 * Session Manager — orchestrate idle timer + multi-tab broadcast + logout flow.
 *
 * Pattern: mount sebagai child di main App. Auto-start saat user authenticated,
 * auto-stop saat logout.
 *
 * Behaviors:
 * - Idle > 30 min → call backend /auth/logout (revoke refresh) + clearAuth + broadcast
 * - Receive LOGOUT broadcast dari tab lain → clearAuth + redirect /login
 * - Show notification saat auto-logout (idle / token expired)
 */

import { App as AntApp } from 'antd';
import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiClient } from '@/api/client';
import { IdleTimer } from '@/lib/idleTimer';
import { broadcastLogout, onSessionMessage } from '@/lib/sessionBroadcast';
import { useAuthStore } from '@/store/auth';

const IDLE_MINUTES = 30;

export function SessionManager() {
  const navigate = useNavigate();
  const { notification } = AntApp.useApp();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const clearAuth = useAuthStore((s) => s.clearAuth);
  const timerRef = useRef<IdleTimer | null>(null);

  // Idle timer
  useEffect(() => {
    if (!isAuthenticated) {
      timerRef.current?.stop();
      timerRef.current = null;
      return;
    }

    const timer = new IdleTimer({
      idleMs: IDLE_MINUTES * 60 * 1000,
      onIdle: async () => {
        const currentRefresh = useAuthStore.getState().refreshToken;
        // Call backend logout untuk revoke refresh token
        if (currentRefresh) {
          try {
            await apiClient.post('/api/v1/auth/logout', { refresh_token: currentRefresh });
          } catch {
            // Best-effort — kalau gagal, tetap clearAuth lokal
          }
        }
        clearAuth();
        broadcastLogout('idle');
        notification.warning({
          message: 'Session berakhir',
          description: `Anda idle ${IDLE_MINUTES} menit. Silakan login ulang untuk lanjut.`,
          placement: 'topRight',
          duration: 6,
        });
        navigate('/login');
      },
    });

    timer.start();
    timerRef.current = timer;
    return () => timer.stop();
  }, [isAuthenticated, navigate, clearAuth, notification]);

  // Multi-tab broadcast listener
  useEffect(() => {
    const unsubscribe = onSessionMessage((msg) => {
      if (msg.type === 'LOGOUT' && useAuthStore.getState().isAuthenticated) {
        clearAuth();
        const reasonText = {
          user: 'Anda logout dari tab lain.',
          idle: 'Session berakhir karena idle di tab lain.',
          'token-expired': 'Session expired. Silakan login ulang.',
        }[msg.reason];

        notification.info({
          message: 'Session berakhir',
          description: reasonText,
          placement: 'topRight',
          duration: 5,
        });
        navigate('/login');
      }
    });
    return unsubscribe;
  }, [clearAuth, navigate, notification]);

  // refreshToken passed sebagai dependency untuk re-render kalau berubah,
  // tapi tidak digunakan langsung di effect (useAuthStore.getState() dipakai untuk fresh value).
  void refreshToken;

  return null; // Component tanpa render, hanya side effects
}
