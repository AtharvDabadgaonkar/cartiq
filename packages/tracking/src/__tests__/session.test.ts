import { describe, expect, it } from 'vitest';
import {
  SESSION_TIMEOUT_MS,
  detectDevice,
  detectTrafficSource,
  memoryStore,
  resolveContext,
  resolveSessionId,
  resolveUserId,
} from '../session';

const IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148';
const IPAD = 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148';
const MAC = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131';
const ANDROID_PHONE =
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile Chrome/131';
const ANDROID_TABLET = 'Mozilla/5.0 (Linux; Android 14; SM-X200) AppleWebKit/537.36 Chrome/131';

describe('detectDevice', () => {
  it('classifies phones, tablets and desktops', () => {
    expect(detectDevice(IPHONE)).toBe('mobile');
    expect(detectDevice(ANDROID_PHONE)).toBe('mobile');
    expect(detectDevice(IPAD)).toBe('tablet');
    expect(detectDevice(ANDROID_TABLET)).toBe('tablet');
    expect(detectDevice(MAC)).toBe('desktop');
  });

  it('falls back to viewport width for unknown agents', () => {
    expect(detectDevice('custom-agent', 390)).toBe('mobile');
    expect(detectDevice('custom-agent', 1440)).toBe('desktop');
  });
});

describe('detectTrafficSource', () => {
  it('prefers an explicit utm_medium', () => {
    expect(detectTrafficSource('/?utm_medium=cpc', 'https://www.google.com/')).toBe('paid_search');
    expect(detectTrafficSource('/?utm_medium=email', '')).toBe('email');
    expect(detectTrafficSource('/?utm_medium=paid_social', '')).toBe('social');
  });

  it('treats click ids as paid', () => {
    expect(detectTrafficSource('/?gclid=abc', '')).toBe('paid_search');
  });

  it('classifies referrer hosts', () => {
    expect(detectTrafficSource('/', 'https://www.google.com/search?q=shoes')).toBe('organic');
    expect(detectTrafficSource('/', 'https://www.instagram.com/p/1')).toBe('social');
    expect(detectTrafficSource('/', 'https://someblog.dev/post')).toBe('referral');
  });

  it('defaults to direct with no referrer, and tolerates junk', () => {
    expect(detectTrafficSource('/', '')).toBe('direct');
    expect(detectTrafficSource('/', 'not-a-url')).toBe('direct');
  });
});

describe('resolveSessionId', () => {
  it('reuses a live session and refreshes its last_seen', () => {
    const store = memoryStore();
    const first = resolveSessionId(store, 1_000);
    const second = resolveSessionId(store, 1_000 + SESSION_TIMEOUT_MS - 1);
    expect(second.id).toBe(first.id);
    expect(second.isNew).toBe(false);
  });

  it('rotates the session after the inactivity timeout', () => {
    const store = memoryStore();
    const first = resolveSessionId(store, 1_000);
    const second = resolveSessionId(store, 1_000 + SESSION_TIMEOUT_MS);
    expect(second.id).not.toBe(first.id);
    expect(second.isNew).toBe(true);
  });

  it('recovers from a corrupt stored value', () => {
    const store = memoryStore({ 'cartiq.session': 'not-json' });
    expect(resolveSessionId(store, 1_000).isNew).toBe(true);
  });
});

describe('resolveUserId', () => {
  it('mints once, then reuses', () => {
    const store = memoryStore();
    const first = resolveUserId(store);
    expect(first.isNewUser).toBe(true);
    const second = resolveUserId(store);
    expect(second.id).toBe(first.id);
    expect(second.isNewUser).toBe(false);
  });
});

describe('resolveContext', () => {
  it('assembles a complete tracker context', () => {
    const ctx = resolveContext({
      url: 'http://localhost:3000/product/sku-1?utm_medium=email',
      referrer: '',
      userAgent: IPHONE,
      persistentStore: memoryStore(),
      sessionStore: memoryStore(),
      nowMs: 1_000,
    });
    expect(ctx).toMatchObject({
      device: 'mobile',
      traffic_source: 'email',
      is_new_user: true,
      page: '/product/sku-1',
      experiment_assignments: {},
    });
    expect(ctx.session_id).toMatch(/^sess_/);
    expect(ctx.user_id).toMatch(/^user_/);
  });
});
