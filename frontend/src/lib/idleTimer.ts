/**
 * Idle timer — track user activity, fire callback setelah idle > timeout.
 *
 * Track events: mousemove, keydown, scroll, click, touchstart.
 * Reset timer setiap event. Fire onIdle setelah `idleMs` tanpa activity.
 *
 * Per NC-SYS-001-02: session expire saat user idle. Frontend trigger logout
 * + show "Session expired" notification.
 */

export interface IdleTimerOptions {
  /** Idle threshold in milliseconds. Default 30 minutes. */
  idleMs?: number;
  /** Callback yang dipanggil saat idle threshold tercapai. */
  onIdle: () => void;
  /** Optional callback saat user resume activity setelah warning. */
  onActive?: () => void;
}

const DEFAULT_IDLE_MS = 30 * 60 * 1000; // 30 menit

const ACTIVITY_EVENTS = [
  'mousemove',
  'mousedown',
  'keydown',
  'scroll',
  'touchstart',
  'click',
];

export class IdleTimer {
  private timerId: number | null = null;
  private readonly idleMs: number;
  private readonly onIdle: () => void;
  private readonly onActive?: () => void;
  private isStarted = false;
  private isIdle = false;
  private boundReset: () => void;

  constructor({ idleMs = DEFAULT_IDLE_MS, onIdle, onActive }: IdleTimerOptions) {
    this.idleMs = idleMs;
    this.onIdle = onIdle;
    this.onActive = onActive;
    this.boundReset = this.reset.bind(this);
  }

  start(): void {
    if (this.isStarted) return;
    this.isStarted = true;
    ACTIVITY_EVENTS.forEach((evt) =>
      window.addEventListener(evt, this.boundReset, { passive: true }),
    );
    this.reset();
  }

  stop(): void {
    if (!this.isStarted) return;
    this.isStarted = false;
    if (this.timerId !== null) {
      window.clearTimeout(this.timerId);
      this.timerId = null;
    }
    ACTIVITY_EVENTS.forEach((evt) =>
      window.removeEventListener(evt, this.boundReset),
    );
  }

  reset(): void {
    if (this.isIdle && this.onActive) {
      this.onActive();
    }
    this.isIdle = false;
    if (this.timerId !== null) {
      window.clearTimeout(this.timerId);
    }
    this.timerId = window.setTimeout(() => {
      this.isIdle = true;
      this.onIdle();
    }, this.idleMs);
  }
}
