import { eventBatchSchema, eventSchema, type CartIQEvent, type EventType } from '@cartiq/shared';
import type { Tracker, TrackerContext, TrackerOptions, TrackPayload, Transport } from './types';

const DEFAULT_BATCH_SIZE = 20;
const DEFAULT_FLUSH_INTERVAL_MS = 5_000;

/** Query strings and fragments routinely carry PII and session tokens. */
export function normalisePage(page: string): string {
  const withoutFragment = page.split('#')[0] ?? '';
  const withoutQuery = withoutFragment.split('?')[0] ?? '';
  const trimmed = withoutQuery.replace(/\/+$/, '');
  return trimmed === '' ? '/' : trimmed;
}

function randomUuid(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID();
  // Fallback for older runtimes; only used for event ids, never for secrets.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** Default transport: sendBeacon on unload, fetch otherwise. */
export function createHttpTransport(endpoint: string): Transport {
  return {
    async send(body, { final }) {
      if (final && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
        const queued = navigator.sendBeacon(
          endpoint,
          new Blob([body], { type: 'application/json' }),
        );
        if (queued) return;
        // Fall through to fetch when the beacon queue is full.
      }
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body,
        keepalive: final,
      });
      if (!response.ok) throw new Error(`event delivery failed: ${response.status}`);
    },
  };
}

export function createTracker(options: TrackerOptions): Tracker {
  const {
    endpoint,
    transport = createHttpTransport(endpoint),
    batchSize = DEFAULT_BATCH_SIZE,
    flushIntervalMs = DEFAULT_FLUSH_INTERVAL_MS,
    now = () => new Date(),
    onInvalid = (error, event) => console.error('[cartiq] invalid event dropped', error, event),
    onDropped = (events, error) => console.warn('[cartiq] dropped batch', events.length, error),
    enabled = true,
  } = options;

  const context: TrackerContext = {
    ...options.context,
    page: normalisePage(options.context.page),
    experiment_assignments: { ...options.context.experiment_assignments },
  };

  let queue: CartIQEvent[] = [];
  let timer: ReturnType<typeof setInterval> | undefined;
  let inFlight: Promise<void> = Promise.resolve();
  let destroyed = false;

  function scheduleFlush() {
    if (timer !== undefined || flushIntervalMs <= 0 || destroyed) return;
    timer = setInterval(() => void flush(), flushIntervalMs);
    // Never hold a Node process open for telemetry.
    (timer as unknown as { unref?: () => void }).unref?.();
  }

  function clearFlushTimer() {
    if (timer !== undefined) {
      clearInterval(timer);
      timer = undefined;
    }
  }

  async function deliver(batch: CartIQEvent[], final: boolean): Promise<void> {
    const body = JSON.stringify(
      eventBatchSchema.parse({ events: batch, sent_at: now().toISOString() }),
    );
    try {
      await transport.send(body, { final });
    } catch (error) {
      if (final) {
        // No second chance during unload.
        onDropped(batch, error);
        return;
      }
      try {
        await transport.send(body, { final: false });
      } catch (retryError) {
        onDropped(batch, retryError);
      }
    }
  }

  async function flush(opts: { final?: boolean } = {}): Promise<void> {
    const final = opts.final ?? false;
    if (queue.length === 0) return;
    // Chunk so one oversized burst cannot exceed the batch cap the API enforces.
    const batches: CartIQEvent[][] = [];
    for (let i = 0; i < queue.length; i += 100) batches.push(queue.slice(i, i + 100));
    queue = [];
    inFlight = inFlight.then(async () => {
      for (const batch of batches) await deliver(batch, final);
    });
    await inFlight;
  }

  function track(eventType: EventType, payload: TrackPayload = {}): void {
    if (!enabled || destroyed) return;
    const candidate = {
      event_id: randomUuid(),
      event_type: eventType,
      timestamp: now().toISOString(),
      user_id: context.user_id,
      session_id: context.session_id,
      device: context.device,
      traffic_source: context.traffic_source,
      is_new_user: context.is_new_user,
      page: normalisePage(payload.page ?? context.page),
      experiment_assignments: { ...context.experiment_assignments },
      properties: payload.properties ?? {},
      ...(payload.product_id !== undefined ? { product_id: payload.product_id } : {}),
      ...(payload.price !== undefined ? { price: payload.price } : {}),
      ...(payload.quantity !== undefined ? { quantity: payload.quantity } : {}),
    };

    // Validate at the edge: a malformed event is dropped here rather than
    // corrupting the warehouse and every metric built on it.
    const result = eventSchema.safeParse(candidate);
    if (!result.success) {
      onInvalid(result.error, candidate);
      return;
    }

    queue.push(result.data);
    scheduleFlush();
    if (queue.length >= batchSize) void flush();
  }

  return {
    track,
    identify(userId) {
      context.user_id = userId;
    },
    setPage(page) {
      context.page = normalisePage(page);
    },
    setExperimentAssignments(assignments) {
      Object.assign(context.experiment_assignments, assignments);
    },
    getContext() {
      return context;
    },
    pending() {
      return queue;
    },
    flush,
    destroy() {
      destroyed = true;
      clearFlushTimer();
      queue = [];
    },
  };
}
