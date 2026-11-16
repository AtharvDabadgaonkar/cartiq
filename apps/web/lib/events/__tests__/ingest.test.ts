import { describe, expect, it } from 'vitest';
import { parseBatch, toEventRow } from '../ingest';

const event = {
  event_id: '6f1b8c2e-4a2d-4f1a-9c3b-0d5e7a9b1c2d',
  event_type: 'purchase' as const,
  timestamp: '2026-03-01T12:00:00.000Z',
  user_id: 'user_42',
  session_id: 'sess_1',
  device: 'mobile' as const,
  traffic_source: 'email' as const,
  is_new_user: false,
  page: '/checkout/confirm',
  price: 128.409,
  quantity: 2,
  experiment_assignments: { flagship_assistant_nudges: 'treatment' },
  properties: { order_id: 'ord_1' },
};

const batch = (events: unknown[]) => ({ events, sent_at: '2026-03-01T12:00:01.000Z' });

describe('toEventRow', () => {
  it('maps wire fields to column names and rounds price to 2dp', () => {
    const row = toEventRow({ ...event, properties: {}, experiment_assignments: {} });
    expect(row.id).toBe(event.event_id);
    expect(row.eventType).toBe('purchase');
    expect(row.timestamp.toISOString()).toBe(event.timestamp);
    expect(row.price?.toString()).toBe('128.41');
    expect(row.source).toBe('LIVE_DEMO');
  });

  it('nulls optional fields rather than dropping them', () => {
    const {
      price: _p,
      quantity: _q,
      product_id: _pid,
      ...bare
    } = { ...event, product_id: undefined };
    const row = toEventRow({ ...bare, properties: {}, experiment_assignments: {} });
    expect(row.price).toBeNull();
    expect(row.quantity).toBeNull();
    expect(row.productId).toBeNull();
  });
});

describe('parseBatch', () => {
  it('accepts a valid batch and reports client lag', () => {
    const result = parseBatch(batch([event]), new Date('2026-03-01T12:00:02.500Z'));
    expect(result.ok).toBe(true);
    expect(result.rows).toHaveLength(1);
    expect(result.lagMs).toBe(1500);
  });

  it('rejects a malformed batch with readable issues', () => {
    const result = parseBatch(batch([{ ...event, event_type: 'nope' }]));
    expect(result.ok).toBe(false);
    expect(result.errors.join()).toContain('event_type');
  });

  it('rejects a body that is not a batch at all', () => {
    expect(parseBatch({ foo: 'bar' }).ok).toBe(false);
    expect(parseBatch(null).ok).toBe(false);
  });

  it('collapses duplicate event ids inside one batch', () => {
    const result = parseBatch(batch([event, event]));
    expect(result.ok).toBe(true);
    expect(result.rows).toHaveLength(1);
  });

  it('preserves experiment assignments and properties verbatim', () => {
    const [row] = parseBatch(batch([event])).rows;
    expect(row!.experimentAssignments).toEqual({ flagship_assistant_nudges: 'treatment' });
    expect(row!.properties).toEqual({ order_id: 'ord_1' });
  });
});
