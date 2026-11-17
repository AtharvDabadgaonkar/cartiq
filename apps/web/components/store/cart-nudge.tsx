'use client';

import { Info } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { Nudge } from '@cartiq/shared';
import { useTracker } from '@/components/providers/tracking-provider';

/**
 * Risk-triggered cart nudge.
 *
 * The decision is made server-side (`/api/cart-risk`): the model scores the
 * cart, the flags decide which messages are live, and the rule ladder picks at
 * most one. The client only renders what it is told and measures what happened.
 */
export function CartNudge({
  cartValue,
  items,
  lines,
}: {
  cartValue: number;
  items: number;
  lines: number;
}) {
  const tracker = useTracker();
  const [nudge, setNudge] = useState<Nudge | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const requested = useRef('');

  useEffect(() => {
    if (lines === 0) return;
    const key = `${cartValue}:${items}:${lines}`;
    if (requested.current === key) return;
    requested.current = key;

    const controller = new AbortController();
    const unitId = readUnitId();

    void (async () => {
      try {
        const response = await fetch('/api/cart-risk', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            unitId,
            cartValue,
            items,
            lines,
            device: guessDevice(),
          }),
          signal: controller.signal,
        });
        if (!response.ok) return;
        const data = (await response.json()) as { nudge: Nudge | null };
        setNudge(data.nudge);
      } catch {
        // A nudge is an enhancement. If scoring fails the cart still works.
      }
    })();

    return () => {
      controller.abort();
      // Release the dedupe key for the request we just cancelled. React
      // StrictMode mounts, unmounts and remounts effects in development, so
      // without this the first fetch is aborted, the ref still holds the key,
      // and the remount returns early — the nudge then never loads at all.
      if (requested.current === key) requested.current = '';
    };
  }, [cartValue, items, lines]);

  useEffect(() => {
    if (!nudge) return;
    tracker.track('nudge_shown', {
      properties: { nudge: nudge.key, flag: nudge.flag, rationale: nudge.rationale },
    });
  }, [nudge, tracker]);

  if (!nudge || dismissed) return null;

  return (
    <aside
      aria-live="polite"
      data-testid="cart-nudge"
      data-nudge={nudge.key}
      className="border-primary/40 bg-primary/10 rounded-lg border p-4"
    >
      <div className="flex items-start gap-3">
        <Info aria-hidden className="text-primary mt-0.5 h-4 w-4 shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-semibold">{nudge.headline}</p>
          <p className="text-muted-foreground mt-1 text-sm">{nudge.body}</p>
        </div>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground rounded px-1 text-xs"
          onClick={() => {
            setDismissed(true);
            // Dismissals are a guardrail metric: a nudge people close is a
            // nudge that is costing goodwill, whatever it does to conversion.
            tracker.track('nudge_clicked', {
              properties: { nudge: nudge.key, action: 'dismiss' },
            });
          }}
        >
          Dismiss<span className="sr-only"> this message</span>
        </button>
      </div>
    </aside>
  );
}

/** The tracking SDK's pseudonymous id, so flags and events agree on the unit. */
function readUnitId(): string {
  try {
    return window.localStorage.getItem('cartiq.user') ?? 'anonymous';
  } catch {
    return 'anonymous';
  }
}

function guessDevice(): 'desktop' | 'mobile' | 'tablet' {
  if (typeof window === 'undefined') return 'desktop';
  const ua = navigator.userAgent.toLowerCase();
  if (/ipad|tablet/.test(ua)) return 'tablet';
  if (/mobi|iphone|android/.test(ua)) return 'mobile';
  return window.innerWidth < 768 ? 'mobile' : 'desktop';
}
