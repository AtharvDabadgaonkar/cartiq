import { beforeEach, describe, expect, it, vi } from 'vitest';
import { eventBatchSchema } from '@cartiq/shared';
import { createTracker, normalisePage } from '../tracker';
import type { TrackerContext, Transport } from '../types';

const context: TrackerContext = {
  session_id: 'sess_1',
  user_id: 'user_1',
  device: 'desktop',
  traffic_source: 'organic',
  is_new_user: true,
  page: '/',
  experiment_assignments: {},
};

function recordingTransport() {
  const batches: ReturnType<typeof eventBatchSchema.parse>[] = [];
  const transport: Transport = {
    async send(body) {
      batches.push(eventBatchSchema.parse(JSON.parse(body)));
    },
  };
  return { transport, batches, events: () => batches.flatMap((b) => b.events) };
}

describe('normalisePage', () => {
  it('strips query strings, fragments and trailing slashes', () => {
    expect(normalisePage('/search?q=shoes&utm_source=x')).toBe('/search');
    expect(normalisePage('/product/1#reviews')).toBe('/product/1');
    expect(normalisePage('/category/shoes/')).toBe('/category/shoes');
    expect(normalisePage('/')).toBe('/');
  });
});

describe('createTracker', () => {
  let rec: ReturnType<typeof recordingTransport>;

  beforeEach(() => {
    rec = recordingTransport();
  });

  it('stamps context onto every event and emits a schema-valid batch', async () => {
    const tracker = createTracker({ endpoint: '/api/events', context, transport: rec.transport });
    tracker.track('product_view', { product_id: 'sku-1', price: 42.5 });
    await tracker.flush();

    const [event] = rec.events();
    expect(event).toMatchObject({
      event_type: 'product_view',
      session_id: 'sess_1',
      user_id: 'user_1',
      device: 'desktop',
      product_id: 'sku-1',
      price: 42.5,
    });
    expect(event!.event_id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('auto-flushes once the batch size is reached', async () => {
    const tracker = createTracker({
      endpoint: '/api/events',
      context,
      transport: rec.transport,
      batchSize: 3,
      flushIntervalMs: 0,
    });
    tracker.track('page_view');
    tracker.track('page_view');
    expect(rec.events()).toHaveLength(0);
    tracker.track('page_view');
    await tracker.flush();
    expect(rec.events()).toHaveLength(3);
  });

  it('drops an invalid event instead of poisoning the batch', async () => {
    const onInvalid = vi.fn();
    const tracker = createTracker({
      endpoint: '/api/events',
      context,
      transport: rec.transport,
      onInvalid,
    });
    tracker.track('add_to_cart', { price: -5 });
    tracker.track('add_to_cart', { price: 5 });
    await tracker.flush();

    expect(onInvalid).toHaveBeenCalledOnce();
    expect(rec.events()).toHaveLength(1);
    expect(rec.events()[0]!.price).toBe(5);
  });

  it('retries a failed batch once, then reports it as dropped', async () => {
    const onDropped = vi.fn();
    const send = vi.fn().mockRejectedValue(new Error('offline'));
    const tracker = createTracker({
      endpoint: '/api/events',
      context,
      transport: { send },
      onDropped,
    });
    tracker.track('page_view');
    await tracker.flush();

    expect(send).toHaveBeenCalledTimes(2);
    expect(onDropped).toHaveBeenCalledOnce();
  });

  it('does not retry during unload', async () => {
    const onDropped = vi.fn();
    const send = vi.fn().mockRejectedValue(new Error('unloading'));
    const tracker = createTracker({
      endpoint: '/api/events',
      context,
      transport: { send },
      onDropped,
    });
    tracker.track('page_view');
    await tracker.flush({ final: true });

    expect(send).toHaveBeenCalledOnce();
    expect(onDropped).toHaveBeenCalledOnce();
  });

  it('carries experiment assignments onto events tracked after assignment', async () => {
    const tracker = createTracker({ endpoint: '/api/events', context, transport: rec.transport });
    tracker.track('page_view');
    tracker.setExperimentAssignments({ flagship_assistant_nudges: 'treatment' });
    tracker.track('add_to_cart', { product_id: 'sku-1' });
    await tracker.flush();

    const [first, second] = rec.events();
    expect(first!.experiment_assignments).toEqual({});
    expect(second!.experiment_assignments).toEqual({ flagship_assistant_nudges: 'treatment' });
  });

  it('upgrades an anonymous visitor on identify', async () => {
    const tracker = createTracker({
      endpoint: '/api/events',
      context: { ...context, user_id: null },
      transport: rec.transport,
    });
    tracker.track('session_start');
    tracker.identify('user_99');
    tracker.track('purchase', { price: 10 });
    await tracker.flush();

    expect(rec.events()[0]!.user_id).toBeNull();
    expect(rec.events()[1]!.user_id).toBe('user_99');
  });

  it('splits an oversized burst into API-sized batches', async () => {
    const tracker = createTracker({
      endpoint: '/api/events',
      context,
      transport: rec.transport,
      batchSize: 1000,
      flushIntervalMs: 0,
    });
    for (let i = 0; i < 150; i++) tracker.track('page_view');
    await tracker.flush();

    expect(rec.batches).toHaveLength(2);
    expect(rec.batches[0]!.events).toHaveLength(100);
    expect(rec.batches[1]!.events).toHaveLength(50);
  });

  it('sends nothing when disabled or destroyed', async () => {
    const disabled = createTracker({
      endpoint: '/api/events',
      context,
      transport: rec.transport,
      enabled: false,
    });
    disabled.track('page_view');
    await disabled.flush();
    expect(rec.events()).toHaveLength(0);

    const tracker = createTracker({ endpoint: '/api/events', context, transport: rec.transport });
    tracker.destroy();
    tracker.track('page_view');
    await tracker.flush();
    expect(rec.events()).toHaveLength(0);
  });
});
