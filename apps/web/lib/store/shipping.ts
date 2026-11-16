/**
 * Shipping rules for the demo store.
 *
 * Mirrors the simulator's economics (`free_shipping_threshold`,
 * `shipping_cost` in docs/SIMULATION.md) so the storefront a shopper sees and
 * the sessions the simulator generates price an order the same way.
 */
export const FREE_SHIPPING_THRESHOLD = 40.0;
export const SHIPPING_COST = 4.95;
export const CURRENCY = 'GBP';

export function shippingFor(subtotal: number): number {
  return subtotal >= FREE_SHIPPING_THRESHOLD || subtotal === 0 ? 0 : SHIPPING_COST;
}

export function amountToFreeShipping(subtotal: number): number {
  return Math.max(0, Math.round((FREE_SHIPPING_THRESHOLD - subtotal) * 100) / 100);
}

export function orderTotal(subtotal: number): number {
  return Math.round((subtotal + shippingFor(subtotal)) * 100) / 100;
}
