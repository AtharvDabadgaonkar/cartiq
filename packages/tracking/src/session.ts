/**
 * Browser-side session + attribution resolution.
 *
 * Deliberately dependency-free and storage-injectable so it can be unit tested
 * in Node and reused by the Playwright suite.
 */
import type { Device, TrafficSource } from '@cartiq/shared';
import type { TrackerContext } from './types';

/** Industry-standard 30 minutes of inactivity ends a session. */
export const SESSION_TIMEOUT_MS = 30 * 60 * 1000;

const SESSION_KEY = 'cartiq.session';
const USER_KEY = 'cartiq.user';

/** Minimal subset of the Storage interface, so tests can pass a plain Map. */
export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function memoryStore(initial: Record<string, string> = {}): KeyValueStore {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => void map.set(k, v),
  };
}

export function detectDevice(userAgent: string, viewportWidth?: number): Device {
  const ua = userAgent.toLowerCase();
  if (/ipad|tablet|playbook|silk|android(?!.*mobile)/.test(ua)) return 'tablet';
  if (/mobi|iphone|ipod|android|blackberry|windows phone/.test(ua)) return 'mobile';
  // Touch laptops and unknown agents fall back to viewport width.
  if (viewportWidth !== undefined && viewportWidth < 768) return 'mobile';
  return 'desktop';
}

/**
 * Last-touch attribution. utm_medium wins when present, because it is the
 * explicit declaration; otherwise the referrer host is classified.
 */
export function detectTrafficSource(url: string, referrer: string): TrafficSource {
  let params: URLSearchParams;
  try {
    params = new URL(url, 'http://localhost').searchParams;
  } catch {
    params = new URLSearchParams();
  }

  const medium = params.get('utm_medium')?.toLowerCase() ?? '';
  if (medium === 'cpc' || medium === 'ppc' || medium === 'paid_search') return 'paid_search';
  if (medium === 'email') return 'email';
  if (medium === 'social' || medium === 'paid_social') return 'social';
  if (medium === 'organic') return 'organic';
  if (medium === 'referral') return 'referral';
  if (params.get('gclid') || params.get('msclkid')) return 'paid_search';

  if (!referrer) return 'direct';
  let host: string;
  try {
    host = new URL(referrer).hostname.toLowerCase();
  } catch {
    return 'direct';
  }
  if (/(^|\.)(google|bing|duckduckgo|yahoo|ecosia|brave)\./.test(host)) return 'organic';
  if (
    /(^|\.)(facebook|instagram|tiktok|reddit|pinterest|x|twitter|linkedin|threads)\./.test(host)
  ) {
    return 'social';
  }
  return 'referral';
}

interface StoredSession {
  id: string;
  last_seen: number;
}

function newId(prefix: string): string {
  const random =
    typeof globalThis.crypto?.randomUUID === 'function'
      ? globalThis.crypto.randomUUID()
      : Math.random().toString(36).slice(2) + Date.now().toString(36);
  return `${prefix}_${random.replace(/-/g, '').slice(0, 24)}`;
}

/**
 * Returns the live session id, rotating it after the inactivity timeout.
 * `store` should be sessionStorage-like but localStorage works too; the
 * timestamp check is what actually bounds the session.
 */
export function resolveSessionId(
  store: KeyValueStore,
  nowMs: number,
): { id: string; isNew: boolean } {
  const raw = store.getItem(SESSION_KEY);
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as StoredSession;
      if (typeof parsed.id === 'string' && nowMs - parsed.last_seen < SESSION_TIMEOUT_MS) {
        store.setItem(SESSION_KEY, JSON.stringify({ id: parsed.id, last_seen: nowMs }));
        return { id: parsed.id, isNew: false };
      }
    } catch {
      // Corrupt value: fall through and start a fresh session.
    }
  }
  const id = newId('sess');
  store.setItem(SESSION_KEY, JSON.stringify({ id, last_seen: nowMs }));
  return { id, isNew: true };
}

/** Returns the persistent pseudonymous user id, minting one on first visit. */
export function resolveUserId(store: KeyValueStore): { id: string; isNewUser: boolean } {
  const existing = store.getItem(USER_KEY);
  if (existing) return { id: existing, isNewUser: false };
  const id = newId('user');
  store.setItem(USER_KEY, id);
  return { id, isNewUser: true };
}

export interface ResolveContextInput {
  url: string;
  referrer: string;
  userAgent: string;
  viewportWidth?: number;
  /** Survives a tab close, so it holds the user id. */
  persistentStore: KeyValueStore;
  /** Cleared when the tab closes, so it holds the session. */
  sessionStore: KeyValueStore;
  nowMs?: number;
}

/** Assembles the full tracker context from the browser environment. */
export function resolveContext(input: ResolveContextInput): TrackerContext {
  const nowMs = input.nowMs ?? Date.now();
  const user = resolveUserId(input.persistentStore);
  const session = resolveSessionId(input.sessionStore, nowMs);
  return {
    session_id: session.id,
    user_id: user.id,
    device: detectDevice(input.userAgent, input.viewportWidth),
    traffic_source: detectTrafficSource(input.url, input.referrer),
    is_new_user: user.isNewUser,
    page: new URL(input.url, 'http://localhost').pathname,
    experiment_assignments: {},
  };
}
