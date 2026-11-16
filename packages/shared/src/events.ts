/**
 * CartIQ event schema — the single source of truth.
 *
 * Every producer (storefront, tracking SDK, session simulator, ingest script)
 * and every consumer (API, SQL models, experiment engine) derives its shape
 * from this file. The Python side mirrors it in `apps/api/src/cartiq_api/schemas/events.py`;
 * `packages/shared/src/__tests__/parity.test.ts` asserts the two stay in sync.
 */
import { z } from 'zod';

/** Ordered so index position doubles as funnel depth where that is useful. */
export const EVENT_TYPES = [
  'session_start',
  'page_view',
  'search',
  'product_view',
  'add_to_cart',
  'remove_from_cart',
  'checkout_start',
  'shipping_step',
  'payment_step',
  'purchase',
  'assistant_open',
  'assistant_query',
  'assistant_click',
  'recommendation_impression',
  'recommendation_click',
  'nudge_shown',
  'nudge_clicked',
] as const;

/**
 * `unknown` exists for sources that do not observe the field. The rule across
 * CartIQ: a field a source cannot observe is null or `unknown`, never invented.
 * Real transactional datasets carry no device or attribution signal, so their
 * rows use `unknown` rather than a plausible-looking guess.
 */
export const DEVICES = ['desktop', 'mobile', 'tablet', 'unknown'] as const;

export const TRAFFIC_SOURCES = [
  'direct',
  'organic',
  'paid_search',
  'social',
  'email',
  'referral',
  'unknown',
] as const;

export const eventTypeSchema = z.enum(EVENT_TYPES);
export const deviceSchema = z.enum(DEVICES);
export const trafficSourceSchema = z.enum(TRAFFIC_SOURCES);

/** JSON-serialisable leaf values allowed inside `properties`. */
const jsonPrimitive = z.union([z.string(), z.number(), z.boolean(), z.null()]);
const propertyValue = z.union([jsonPrimitive, z.array(jsonPrimitive)]);

/**
 * Map of experiment key -> assigned variant key, stamped onto every event so
 * any metric can be sliced by any live experiment without a join at write time.
 */
export const experimentAssignmentsSchema = z.record(z.string().min(1), z.string().min(1));

export const eventSchema = z.object({
  /** UUID v4. Primary key; makes ingestion idempotent. */
  event_id: z.string().uuid(),
  event_type: eventTypeSchema,
  /** ISO-8601 with timezone. Stored as timestamptz. */
  timestamp: z.string().datetime({ offset: true }),
  /** Stable pseudonymous id. Null for a first-touch anonymous visitor. */
  user_id: z.string().min(1).max(64).nullable(),
  session_id: z.string().min(1).max(64),
  device: deviceSchema,
  traffic_source: trafficSourceSchema,
  /** Null when the source cannot tell (an anonymous, unattributed order line). */
  is_new_user: z.boolean().nullable().default(null),
  /**
   * Route path, e.g. "/product/1234". Query strings are stripped by the SDK.
   * Null for sources with no concept of a page (an imported order line).
   */
  page: z.string().min(1).max(512).nullable().default(null),
  product_id: z.string().min(1).max(64).optional(),
  /** Unit price in minor units is avoided on purpose: the source datasets are decimal. */
  price: z.number().nonnegative().optional(),
  quantity: z.number().int().positive().optional(),
  experiment_assignments: experimentAssignmentsSchema.default({}),
  properties: z.record(z.string(), propertyValue).default({}),
});

/** Payload accepted by POST /api/events — ids and timestamps may be filled in by the SDK. */
export const eventBatchSchema = z.object({
  events: z.array(eventSchema).min(1).max(100),
  /** Set by the SDK so the API can measure client->server lag. */
  sent_at: z.string().datetime({ offset: true }),
});

export type EventType = (typeof EVENT_TYPES)[number];
export type Device = (typeof DEVICES)[number];
export type TrafficSource = (typeof TRAFFIC_SOURCES)[number];
export type ExperimentAssignments = z.infer<typeof experimentAssignmentsSchema>;
export type CartIQEvent = z.infer<typeof eventSchema>;
export type EventBatch = z.infer<typeof eventBatchSchema>;

/**
 * Canonical purchase funnel. Module 1 reports drop-off between consecutive
 * steps; `models/` and the API both import this ordering rather than restating it.
 */
export const FUNNEL_STEPS = [
  { key: 'visit', label: 'Visit', eventType: 'session_start' },
  { key: 'browse', label: 'Search / Browse', eventType: 'page_view' },
  { key: 'product_view', label: 'Product View', eventType: 'product_view' },
  { key: 'add_to_cart', label: 'Add to Cart', eventType: 'add_to_cart' },
  { key: 'checkout', label: 'Checkout Start', eventType: 'checkout_start' },
  { key: 'shipping', label: 'Shipping', eventType: 'shipping_step' },
  { key: 'payment', label: 'Payment', eventType: 'payment_step' },
  { key: 'purchase', label: 'Purchase', eventType: 'purchase' },
] as const satisfies ReadonlyArray<{ key: string; label: string; eventType: EventType }>;

export type FunnelStepKey = (typeof FUNNEL_STEPS)[number]['key'];

/** `search` and `page_view` both advance the browse step; keep that in one place. */
export const BROWSE_EVENT_TYPES: readonly EventType[] = ['page_view', 'search'];
