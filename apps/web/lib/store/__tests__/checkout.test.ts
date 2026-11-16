import { beforeEach, describe, expect, it } from 'vitest';
import {
  EMPTY_SHIPPING,
  clearCheckout,
  newOrderId,
  readOrder,
  readShipping,
  saveOrder,
  saveShipping,
  validateShipping,
  type ShippingDetails,
} from '../checkout';

const VALID: ShippingDetails = {
  fullName: 'Demo Shopper',
  email: 'demo@example.com',
  address1: '1 Example Street',
  address2: '',
  city: 'Manchester',
  postcode: 'M1 1AA',
  country: 'United Kingdom',
};

beforeEach(() => {
  window.sessionStorage.clear();
});

describe('validateShipping', () => {
  it('accepts a complete address', () => {
    expect(validateShipping(VALID)).toEqual({});
  });

  it('treats address line 2 as optional', () => {
    expect(validateShipping({ ...VALID, address2: '' })).toEqual({});
  });

  it.each(['fullName', 'address1', 'city', 'postcode'] as const)('requires %s', (field) => {
    const errors = validateShipping({ ...VALID, [field]: '' });
    expect(errors[field]).toBeTruthy();
  });

  it('rejects whitespace-only values, which look filled in', () => {
    expect(validateShipping({ ...VALID, fullName: '   ' }).fullName).toBeTruthy();
  });

  it.each(['not-an-email', 'missing@domain', '@example.com', 'spaces in@example.com'])(
    'rejects the email %s',
    (email) => {
      expect(validateShipping({ ...VALID, email }).email).toBeTruthy();
    },
  );

  it('reports every problem at once, not just the first', () => {
    expect(Object.keys(validateShipping(EMPTY_SHIPPING)).length).toBeGreaterThan(3);
  });
});

describe('persistence', () => {
  it('round-trips the address through sessionStorage', () => {
    saveShipping(VALID);
    expect(readShipping()).toEqual(VALID);
  });

  it('returns null when nothing is stored', () => {
    expect(readShipping()).toBeNull();
    expect(readOrder()).toBeNull();
  });

  it('survives a corrupt stored value rather than throwing', () => {
    window.sessionStorage.setItem('cartiq.checkout.shipping', 'not json');
    expect(readShipping()).toBeNull();
  });

  it('clears the address but keeps the placed order for the confirmation page', () => {
    saveShipping(VALID);
    saveOrder({
      orderId: 'CQ-TEST',
      subtotal: 7.95,
      shipping: 4.95,
      total: 12.9,
      itemCount: 1,
      email: VALID.email,
      placedAt: new Date().toISOString(),
    });

    clearCheckout();

    expect(readShipping()).toBeNull();
    expect(readOrder()?.orderId).toBe('CQ-TEST');
  });
});

describe('newOrderId', () => {
  it('is prefixed and unique', () => {
    const ids = new Set(Array.from({ length: 200 }, () => newOrderId()));
    expect(ids.size).toBe(200);
    for (const id of ids) expect(id).toMatch(/^CQ-[A-Z0-9]+$/);
  });
});
