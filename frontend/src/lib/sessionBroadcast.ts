/**
 * Multi-tab session broadcast via BroadcastChannel API.
 *
 * Pattern: 1 tab logout → broadcast event → all other tabs auto-logout juga.
 * Prevent confused state dimana 1 tab logout tapi tab lain masih login.
 */

type SessionMessage =
  | { type: 'LOGOUT'; reason: 'user' | 'idle' | 'token-expired' }
  | { type: 'LOGIN'; nik: string };

const CHANNEL_NAME = 'idea-session';

let channel: BroadcastChannel | null = null;

function getChannel(): BroadcastChannel | null {
  if (typeof window === 'undefined' || !('BroadcastChannel' in window)) {
    return null; // Fallback no-op untuk SSR / older browsers
  }
  if (channel === null) {
    channel = new BroadcastChannel(CHANNEL_NAME);
  }
  return channel;
}

export function broadcastLogout(reason: 'user' | 'idle' | 'token-expired'): void {
  const ch = getChannel();
  if (ch) ch.postMessage({ type: 'LOGOUT', reason } as SessionMessage);
}

export function broadcastLogin(nik: string): void {
  const ch = getChannel();
  if (ch) ch.postMessage({ type: 'LOGIN', nik } as SessionMessage);
}

export function onSessionMessage(
  handler: (msg: SessionMessage) => void,
): () => void {
  const ch = getChannel();
  if (!ch) return () => {}; // No-op cleanup

  const wrapped = (event: MessageEvent<SessionMessage>) => handler(event.data);
  ch.addEventListener('message', wrapped);
  return () => ch.removeEventListener('message', wrapped);
}

export function closeChannel(): void {
  if (channel !== null) {
    channel.close();
    channel = null;
  }
}
