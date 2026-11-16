import type {
  CartIQEvent,
  Device,
  EventType,
  ExperimentAssignments,
  TrafficSource,
} from '@cartiq/shared';

/** Everything the tracker knows about the current visitor between calls. */
export interface TrackerContext {
  session_id: string;
  user_id: string | null;
  device: Device;
  traffic_source: TrafficSource;
  is_new_user: boolean;
  page: string;
  experiment_assignments: ExperimentAssignments;
}

/** Per-call fields. Everything else is filled in from context. */
export type TrackPayload = Omit<
  Partial<CartIQEvent>,
  'event_id' | 'event_type' | 'timestamp' | keyof TrackerContext
> &
  Partial<Pick<CartIQEvent, 'product_id' | 'price' | 'quantity' | 'properties' | 'page'>>;

export interface Transport {
  /**
   * Delivers a batch. Must not throw: a rejected promise is treated as a
   * delivery failure and the batch is re-queued once.
   * `final` is true during page unload, where only fire-and-forget works.
   */
  send(body: string, options: { final: boolean }): Promise<void>;
}

export interface TrackerOptions {
  endpoint: string;
  context: TrackerContext;
  transport?: Transport;
  /** Events buffered before an automatic flush. */
  batchSize?: number;
  /** Idle milliseconds before an automatic flush. */
  flushIntervalMs?: number;
  /** Injected for tests; defaults to Date/setInterval. */
  now?: () => Date;
  /** Called when an event fails schema validation. Defaults to console.error. */
  onInvalid?: (error: unknown, event: unknown) => void;
  /** Called when a batch cannot be delivered after one retry. */
  onDropped?: (events: CartIQEvent[], error: unknown) => void;
  /** Disables tracking entirely (e.g. a bot or an opted-out visitor). */
  enabled?: boolean;
}

export interface Tracker {
  track(eventType: EventType, payload?: TrackPayload): void;
  /** Promotes an anonymous visitor to a known user id. */
  identify(userId: string): void;
  setPage(page: string): void;
  /** Merges in assignments so later events carry them. */
  setExperimentAssignments(assignments: ExperimentAssignments): void;
  getContext(): Readonly<TrackerContext>;
  /** Pending events, for assertions and debugging. */
  pending(): readonly CartIQEvent[];
  flush(options?: { final?: boolean }): Promise<void>;
  destroy(): void;
}
