import type { Page, Request } from '@playwright/test';

export interface CapturedEvent {
  event_type: string;
  page: string | null;
  product_id?: string;
  price?: number;
  quantity?: number;
  session_id: string;
  properties: Record<string, unknown>;
}

/**
 * Captures the event batches the tracking SDK posts.
 *
 * Intercepting the request rather than reading the database keeps the
 * assertions deterministic and lets the suite run without Postgres state
 * leaking between tests.
 */
export class EventRecorder {
  readonly events: CapturedEvent[] = [];

  private constructor(private readonly page: Page) {}

  static async attach(page: Page): Promise<EventRecorder> {
    const recorder = new EventRecorder(page);
    page.on('request', (request: Request) => {
      if (!request.url().endsWith('/api/events') || request.method() !== 'POST') return;
      // `postData()` returns null for a Blob body, which is exactly what
      // navigator.sendBeacon sends on unload, so fall back to the raw buffer.
      const raw = request.postData() ?? request.postDataBuffer()?.toString('utf8');
      if (!raw) return;
      try {
        const body = JSON.parse(raw) as { events?: CapturedEvent[] };
        recorder.events.push(...(body.events ?? []));
      } catch {
        // A malformed body is itself a failure, surfaced by a missing event.
      }
    });
    return recorder;
  }

  ofType(type: string): CapturedEvent[] {
    return this.events.filter((event) => event.event_type === type);
  }

  types(): string[] {
    return this.events.map((event) => event.event_type);
  }

  /**
   * Forces a flush so queued events are posted before an assertion.
   *
   * Calls the tracker's own flush through the `window.__cartiq` debug hook.
   * Synthetic unload events are not a reliable trigger (visibilityState does
   * not change, and a sendBeacon body is not readable from a test), so the
   * hook is what makes these assertions deterministic.
   */
  async flush(): Promise<void> {
    await this.page
      .evaluate(async () => {
        const hook = (window as Window & { __cartiq?: { flush: () => Promise<void> } }).__cartiq;
        await hook?.flush();
      })
      .catch(() => {
        // The page may be navigating; the next flush will pick the events up.
      });
    await this.page.waitForTimeout(250);
  }

  /** Waits until at least `count` events of a type have been captured. */
  async waitForCount(type: string, count: number, timeoutMs = 8000): Promise<CapturedEvent[]> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      await this.flush();
      const found = this.ofType(type);
      if (found.length >= count) return found;
      await this.page.waitForTimeout(150);
    }
    throw new Error(`expected at least ${count} "${type}" events, saw ${this.ofType(type).length}`);
  }

  async waitFor(type: string, timeoutMs = 8000): Promise<CapturedEvent> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      await this.flush();
      const found = this.ofType(type);
      if (found.length > 0) return found[found.length - 1]!;
      await this.page.waitForTimeout(200);
    }
    throw new Error(
      `event "${type}" was never emitted. Saw: ${[...new Set(this.types())].join(', ') || 'nothing'}`,
    );
  }
}

/** Fills the demo checkout address with obviously fictional details. */
export async function fillShipping(page: Page): Promise<void> {
  await page.getByLabel('Full name').fill('Demo Shopper');
  await page.getByLabel('Email').fill('demo@example.com');
  await page.getByLabel('Address', { exact: true }).fill('1 Example Street');
  await page.getByLabel('Town or city').fill('Manchester');
  await page.getByLabel('Postcode').fill('M1 1AA');
}

/**
 * Adds the first product on the page to the cart and waits for the cart badge
 * to reflect it.
 *
 * The cart persists through a React effect, so navigating immediately after the
 * click can race the write and land on an empty cart.
 */
export async function addFirstProductToCart(page: Page): Promise<void> {
  await page
    .getByRole('button', { name: /^Add to cart/ })
    .first()
    .click();
  // "Cart, 0 items" also matches a lazy \d+, so require a non-zero count:
  // otherwise this returns before the item is actually in the cart.
  await page.getByRole('link', { name: /^Cart, [1-9]\d* item/ }).waitFor({ state: 'visible' });
  // The badge updates on render but the cart is persisted in an effect, so a
  // navigation here can outrun the write and land on an empty cart.
  await page.waitForFunction(() => {
    try {
      return (
        (JSON.parse(window.localStorage.getItem('cartiq.cart') ?? '[]') as unknown[]).length > 0
      );
    } catch {
      return false;
    }
  });
}
