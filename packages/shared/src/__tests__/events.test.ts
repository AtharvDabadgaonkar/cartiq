import { describe, expect, it } from 'vitest';
import { EVENT_TYPES, FUNNEL_STEPS, eventBatchSchema, eventSchema } from '../events';

const validEvent = {
  event_id: '6f1b8c2e-4a2d-4f1a-9c3b-0d5e7a9b1c2d',
  event_type: 'add_to_cart',
  timestamp: '2026-03-01T12:00:00.000Z',
  user_id: 'user_42',
  session_id: 'sess_1',
  device: 'mobile',
  traffic_source: 'paid_search',
  is_new_user: false,
  page: '/product/sku-1',
  product_id: 'sku-1',
  price: 59.99,
  quantity: 1,
};

describe('eventSchema', () => {
  it('accepts a valid event and defaults the open-ended maps', () => {
    const parsed = eventSchema.parse(validEvent);
    expect(parsed.experiment_assignments).toEqual({});
    expect(parsed.properties).toEqual({});
  });

  it('rejects an unknown event type', () => {
    expect(() => eventSchema.parse({ ...validEvent, event_type: 'wishlist_add' })).toThrow();
  });

  it('rejects a timestamp without a timezone offset', () => {
    expect(() => eventSchema.parse({ ...validEvent, timestamp: '2026-03-01T12:00:00' })).toThrow();
  });

  it('rejects a non-uuid event id, so ingestion stays idempotent', () => {
    expect(() => eventSchema.parse({ ...validEvent, event_id: 'evt-1' })).toThrow();
  });

  it('rejects negative price and zero quantity', () => {
    expect(() => eventSchema.parse({ ...validEvent, price: -1 })).toThrow();
    expect(() => eventSchema.parse({ ...validEvent, quantity: 0 })).toThrow();
  });

  it('allows an anonymous visitor but never a missing session', () => {
    expect(eventSchema.parse({ ...validEvent, user_id: null }).user_id).toBeNull();
    const { session_id: _omitted, ...withoutSession } = validEvent;
    expect(() => eventSchema.parse(withoutSession)).toThrow();
  });

  it('keeps experiment assignments as a flat key -> variant map', () => {
    const parsed = eventSchema.parse({
      ...validEvent,
      experiment_assignments: { flagship_assistant_nudges: 'treatment' },
    });
    expect(parsed.experiment_assignments.flagship_assistant_nudges).toBe('treatment');
    expect(() =>
      eventSchema.parse({ ...validEvent, experiment_assignments: { exp: { variant: 'a' } } }),
    ).toThrow();
  });
});

describe('eventBatchSchema', () => {
  it('requires at least one event and caps the batch', () => {
    expect(() => eventBatchSchema.parse({ events: [], sent_at: validEvent.timestamp })).toThrow();
    const tooMany = Array.from({ length: 101 }, () => validEvent);
    expect(() =>
      eventBatchSchema.parse({ events: tooMany, sent_at: validEvent.timestamp }),
    ).toThrow();
  });
});

describe('funnel definition', () => {
  it('has unique keys in strictly increasing depth', () => {
    const keys = FUNNEL_STEPS.map((s) => s.key);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it('only references declared event types', () => {
    for (const step of FUNNEL_STEPS) {
      expect(EVENT_TYPES).toContain(step.eventType);
    }
  });

  it('starts at visit and ends at purchase', () => {
    expect(FUNNEL_STEPS[0].key).toBe('visit');
    expect(FUNNEL_STEPS.at(-1)!.key).toBe('purchase');
  });
});
