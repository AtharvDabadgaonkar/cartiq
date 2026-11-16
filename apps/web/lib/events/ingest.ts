import { eventBatchSchema, type CartIQEvent } from '@cartiq/shared';
import { Prisma } from '@prisma/client';

/**
 * Pure mapping from a validated wire event to a database row.
 * Kept out of the route handler so it is unit-testable without a database.
 */
export type EventRow = {
  id: string;
  eventType: CartIQEvent['event_type'];
  timestamp: Date;
  userId: string | null;
  sessionId: string;
  device: CartIQEvent['device'];
  trafficSource: CartIQEvent['traffic_source'];
  isNewUser: boolean;
  page: string;
  productId: string | null;
  price: Prisma.Decimal | null;
  quantity: number | null;
  experimentAssignments: CartIQEvent['experiment_assignments'];
  properties: CartIQEvent['properties'];
  source: 'LIVE_DEMO' | 'SIMULATED' | 'REAL_DATASET';
};

export function toEventRow(event: CartIQEvent, source: EventRow['source'] = 'LIVE_DEMO'): EventRow {
  return {
    id: event.event_id,
    eventType: event.event_type,
    timestamp: new Date(event.timestamp),
    userId: event.user_id,
    sessionId: event.session_id,
    device: event.device,
    trafficSource: event.traffic_source,
    isNewUser: event.is_new_user,
    page: event.page,
    productId: event.product_id ?? null,
    price: event.price === undefined ? null : new Prisma.Decimal(event.price.toFixed(2)),
    quantity: event.quantity ?? null,
    experimentAssignments: event.experiment_assignments,
    properties: event.properties,
    source,
  };
}

export interface ParseResult {
  ok: boolean;
  rows: EventRow[];
  /** Zod issue strings, returned to the caller for debugging in dev. */
  errors: string[];
  /** Client -> server lag in ms, from the batch's sent_at. */
  lagMs: number | null;
}

/** Validates a raw request body and converts it to rows. */
export function parseBatch(body: unknown, now = new Date()): ParseResult {
  const parsed = eventBatchSchema.safeParse(body);
  if (!parsed.success) {
    return {
      ok: false,
      rows: [],
      errors: parsed.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`),
      lagMs: null,
    };
  }
  // Duplicate event ids inside one batch would make createMany throw even with
  // skipDuplicates, so collapse them here.
  const seen = new Set<string>();
  const rows: EventRow[] = [];
  for (const event of parsed.data.events) {
    if (seen.has(event.event_id)) continue;
    seen.add(event.event_id);
    rows.push(toEventRow(event));
  }
  return {
    ok: true,
    rows,
    errors: [],
    lagMs: now.getTime() - new Date(parsed.data.sent_at).getTime(),
  };
}
