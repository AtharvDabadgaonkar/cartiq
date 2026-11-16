import { describe, expect, it } from 'vitest';
import {
  FREE_SHIPPING_THRESHOLD,
  SHIPPING_COST,
  amountToFreeShipping,
  orderTotal,
  shippingFor,
} from '../shipping';

describe('shippingFor', () => {
  it('charges below the threshold and not at or above it', () => {
    expect(shippingFor(FREE_SHIPPING_THRESHOLD - 0.01)).toBe(SHIPPING_COST);
    expect(shippingFor(FREE_SHIPPING_THRESHOLD)).toBe(0);
    expect(shippingFor(FREE_SHIPPING_THRESHOLD + 10)).toBe(0);
  });

  it('charges nothing for an empty basket', () => {
    expect(shippingFor(0)).toBe(0);
  });
});

describe('amountToFreeShipping', () => {
  it('reports the gap, and zero once it is met', () => {
    expect(amountToFreeShipping(7.95)).toBe(32.05);
    expect(amountToFreeShipping(FREE_SHIPPING_THRESHOLD)).toBe(0);
    expect(amountToFreeShipping(100)).toBe(0);
  });

  it('does not leak floating point noise into the UI', () => {
    // 40 - 0.1 - 0.2 is 39.699999... in binary floating point.
    expect(amountToFreeShipping(0.1 + 0.2)).toBe(39.7);
  });
});

describe('orderTotal', () => {
  it('adds shipping only when it applies', () => {
    expect(orderTotal(7.95)).toBe(12.9);
    expect(orderTotal(45)).toBe(45);
    expect(orderTotal(0)).toBe(0);
  });

  it('rounds to whole pence', () => {
    expect(orderTotal(10.555)).toBe(15.51);
  });
});
