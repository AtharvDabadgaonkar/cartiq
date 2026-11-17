/**
 * Cart-recovery nudge rules.
 *
 * Mirrored by `apps/api/src/cartiq_api/nudges.py`; a parity test fails the
 * build if the thresholds drift. The storefront decides in TypeScript and the
 * console explains the same ladder in Python, so both must agree on when a
 * shopper gets interrupted.
 */

/** Risk above which a cart is worth interrupting at all. */
export const MEDIUM_RISK_THRESHOLD = 0.75;
/** Risk above which the stronger, lower-pressure message is used. */
export const HIGH_RISK_THRESHOLD = 0.85;
/** Only mention free delivery when it is actually within reach. */
export const FREE_SHIPPING_NUDGE_GAP = 15.0;

export const NUDGE_FLAGS = ['nudge_free_shipping', 'nudge_saved_cart', 'nudge_low_stock'] as const;

export type NudgeFlag = (typeof NUDGE_FLAGS)[number];

export interface CartContext {
  cartValue: number;
  items: number;
  riskScore: number;
  paysShipping: boolean;
  gapToFreeShipping: number;
}

export interface Nudge {
  key: 'free_shipping_threshold' | 'saved_cart_reminder' | 'low_stock_note';
  flag: NudgeFlag;
  headline: string;
  body: string;
  rationale: string;
}

/**
 * Picks at most one nudge.
 *
 * At most one on purpose: stacking messages on a hesitant shopper turns a
 * helpful nudge into a dark pattern, and it would make the experiment
 * uninterpretable — you could not say which message moved anyone.
 */
export function chooseNudge(context: CartContext, enabledFlags: ReadonlySet<string>): Nudge | null {
  if (context.riskScore < MEDIUM_RISK_THRESHOLD) return null;

  if (
    enabledFlags.has('nudge_free_shipping') &&
    context.paysShipping &&
    context.gapToFreeShipping > 0 &&
    context.gapToFreeShipping <= FREE_SHIPPING_NUDGE_GAP
  ) {
    return {
      key: 'free_shipping_threshold',
      flag: 'nudge_free_shipping',
      headline: `£${context.gapToFreeShipping.toFixed(2)} from free delivery`,
      body: 'Add a little more and delivery is on us.',
      rationale: `risk ${(context.riskScore * 100).toFixed(0)}% and £${context.gapToFreeShipping.toFixed(2)} short of the threshold`,
    };
  }

  if (enabledFlags.has('nudge_saved_cart') && context.riskScore >= HIGH_RISK_THRESHOLD) {
    return {
      key: 'saved_cart_reminder',
      flag: 'nudge_saved_cart',
      headline: 'Your cart is saved',
      body: 'Take your time — these items will still be here when you come back.',
      rationale: `risk ${(context.riskScore * 100).toFixed(0)}% at or above the high-risk threshold`,
    };
  }

  if (enabledFlags.has('nudge_low_stock') && context.items > 1) {
    return {
      key: 'low_stock_note',
      flag: 'nudge_low_stock',
      headline: 'Popular right now',
      body: 'Items in your cart are selling quickly today.',
      rationale: `risk ${(context.riskScore * 100).toFixed(0)}% with ${context.items} items and no better-matching nudge`,
    };
  }

  return null;
}
