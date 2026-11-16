/**
 * Checkout state, held in sessionStorage.
 *
 * Deliberately never leaves the browser except as the order event: this is a
 * demo store with no backend order service, and keeping the address client-side
 * means no personal data is stored anywhere.
 */

export interface ShippingDetails {
  fullName: string;
  email: string;
  address1: string;
  address2: string;
  city: string;
  postcode: string;
  country: string;
}

export interface PlacedOrder {
  orderId: string;
  subtotal: number;
  shipping: number;
  total: number;
  itemCount: number;
  email: string;
  placedAt: string;
}

const SHIPPING_KEY = 'cartiq.checkout.shipping';
const ORDER_KEY = 'cartiq.checkout.order';

function read<T>(key: string): T | null {
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Private browsing: the step still works, it just will not survive a reload.
  }
}

export const EMPTY_SHIPPING: ShippingDetails = {
  fullName: '',
  email: '',
  address1: '',
  address2: '',
  city: '',
  postcode: '',
  country: 'United Kingdom',
};

export const readShipping = () => read<ShippingDetails>(SHIPPING_KEY);
export const saveShipping = (details: ShippingDetails) => write(SHIPPING_KEY, details);
export const readOrder = () => read<PlacedOrder>(ORDER_KEY);
export const saveOrder = (order: PlacedOrder) => write(ORDER_KEY, order);

export function clearCheckout(): void {
  try {
    window.sessionStorage.removeItem(SHIPPING_KEY);
  } catch {
    // Nothing to clean up.
  }
}

export type ShippingErrors = Partial<Record<keyof ShippingDetails, string>>;

/** Validation deliberately light: enough to exercise the step, not to gatekeep. */
export function validateShipping(details: ShippingDetails): ShippingErrors {
  const errors: ShippingErrors = {};
  if (!details.fullName.trim()) errors.fullName = 'Enter the name for the delivery.';
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(details.email.trim())) {
    errors.email = 'Enter an email address so we can send the confirmation.';
  }
  if (!details.address1.trim()) errors.address1 = 'Enter the street address.';
  if (!details.city.trim()) errors.city = 'Enter the town or city.';
  if (!details.postcode.trim()) errors.postcode = 'Enter the postcode.';
  return errors;
}

export function newOrderId(): string {
  const random =
    typeof crypto?.randomUUID === 'function'
      ? crypto.randomUUID().replace(/-/g, '').slice(0, 10)
      : Math.random().toString(36).slice(2, 12);
  return `CQ-${random.toUpperCase()}`;
}
