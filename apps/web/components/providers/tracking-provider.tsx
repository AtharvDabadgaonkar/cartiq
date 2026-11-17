'use client';

import {
  createTracker,
  memoryStore,
  resolveContext,
  resolveSessionId,
  type Tracker,
} from '@cartiq/tracking';
import { usePathname, useSearchParams } from 'next/navigation';
import { createContext, useContext, useEffect, useMemo, useRef } from 'react';

/**
 * Wires the tracking SDK into the App Router.
 *
 * Responsibilities kept here rather than in the SDK, because they are
 * framework-specific: emitting `session_start` exactly once per session,
 * emitting `page_view` on every client-side navigation, and flushing on unload.
 */

const TrackerContext = createContext<Tracker | null>(null);

/** Safe storage: private browsing and blocked cookies must not break the shop. */
function safeStorage(kind: 'local' | 'session') {
  try {
    const storage = kind === 'local' ? window.localStorage : window.sessionStorage;
    // Touch it: Safari throws on access in some privacy modes rather than on use.
    storage.getItem('cartiq.probe');
    return storage;
  } catch {
    return memoryStore();
  }
}

export function TrackingProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const trackerRef = useRef<Tracker | null>(null);
  const lastPage = useRef<string | null>(null);

  const tracker = useMemo(() => {
    if (typeof window === 'undefined') return null;
    if (trackerRef.current) return trackerRef.current;

    const sessionStore = safeStorage('session');
    const persistentStore = safeStorage('local');
    const context = resolveContext({
      url: window.location.href,
      referrer: document.referrer,
      userAgent: navigator.userAgent,
      viewportWidth: window.innerWidth,
      persistentStore,
      sessionStore,
    });

    const instance = createTracker({ endpoint: '/api/events', context });

    // `resolveContext` already created or refreshed the session; ask whether it
    // was new so `session_start` fires once per session, not once per reload.
    const { isNew } = resolveSessionId(sessionStore, Date.now());
    if (isNew || !sessionStore.getItem('cartiq.session_started')) {
      instance.track('session_start');
      try {
        sessionStore.setItem('cartiq.session_started', '1');
      } catch {
        // Nothing to do: at worst we emit one extra session_start.
      }
    }

    /**
     * Debug/e2e hook. Flushing otherwise only happens on a timer, at the batch
     * size, or on unload via sendBeacon — and a beacon's body is not reliably
     * readable from a test, which makes the funnel assertions flaky. Exposing
     * an explicit flush keeps those tests deterministic. It carries no secrets
     * and cannot emit anything the page could not already emit.
     */
    (window as Window & { __cartiq?: unknown }).__cartiq = {
      flush: (options?: { final?: boolean }) => instance.flush(options),
      pending: () => instance.pending(),
    };

    trackerRef.current = instance;
    return instance;
  }, []);

  // One page_view per navigation, including client-side ones.
  useEffect(() => {
    if (!tracker || !pathname) return;
    const query = searchParams?.toString();
    const key = query ? `${pathname}?${query}` : pathname;
    if (lastPage.current === key) return;
    lastPage.current = key;

    tracker.setPage(pathname);
    tracker.track('page_view', {
      properties: query ? { query_string: query } : {},
    });
  }, [tracker, pathname, searchParams]);

  // Flush queued events while the page is going away.
  useEffect(() => {
    if (!tracker) return;
    const flush = () => void tracker.flush({ final: true });
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') flush();
    };
    window.addEventListener('pagehide', flush);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('pagehide', flush);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [tracker]);

  return <TrackerContext.Provider value={tracker}>{children}</TrackerContext.Provider>;
}

/**
 * Returns a tracker that is always safe to call. Before hydration, or if
 * tracking failed to initialise, the calls are no-ops rather than crashes:
 * analytics must never break the shop.
 */
export function useTracker(): Pick<Tracker, 'track' | 'identify' | 'flush'> {
  const tracker = useContext(TrackerContext);
  return useMemo(
    () => ({
      track: (type, payload) =>
        tracker?.track(type, {
          ...payload,
          /**
           * Read the path at call time rather than relying on the provider's
           * context. A child's effect runs BEFORE its parent's, so a component
           * that tracks on mount would otherwise be stamped with the page it
           * navigated away from — which put `payment_step` on
           * `/checkout/shipping` and made the funnel unreadable by page.
           */
          page: payload?.page ?? window.location.pathname,
        }),
      identify: (userId) => tracker?.identify(userId),
      flush: async (options) => tracker?.flush(options),
    }),
    [tracker],
  );
}
