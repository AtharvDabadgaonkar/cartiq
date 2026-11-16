'use client';

import { Lock, ShieldCheck } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { useCart } from '@/components/providers/cart-provider';
import { useTracker } from '@/components/providers/tracking-provider';
import { CheckoutSteps } from '@/components/store/checkout-steps';
import { OrderSummary } from '@/components/store/order-summary';
import { Button } from '@/components/ui/button';
import {
  clearCheckout,
  newOrderId,
  readShipping,
  saveOrder,
  type ShippingDetails,
} from '@/lib/store/checkout';
import { orderTotal, shippingFor } from '@/lib/store/shipping';

/**
 * Mock payment.
 *
 * There is deliberately no card-number field anywhere in this app. A demo that
 * renders one invites a visitor to type a real card into a toy, so the payment
 * method is a fixed, obviously fake card and the button does nothing but emit
 * the purchase event.
 */
export function PaymentStep() {
  const router = useRouter();
  const { lines, itemCount, subtotal, ready, clear } = useCart();
  const tracker = useTracker();
  const [shipping, setShipping] = useState<ShippingDetails | null>(null);
  /**
   * sessionStorage can only be read in an effect, so `shipping` is null on the
   * first pass even when details exist. Without this flag the guard below
   * bounces straight back to the shipping step and checkout can never advance.
   */
  const [shippingLoaded, setShippingLoaded] = useState(false);
  const [placing, setPlacing] = useState(false);
  const tracked = useRef(false);

  useEffect(() => {
    setShipping(readShipping());
    setShippingLoaded(true);
  }, []);

  useEffect(() => {
    if (tracked.current || !ready || lines.length === 0) return;
    tracked.current = true;
    tracker.track('payment_step', { price: subtotal, quantity: itemCount });
  }, [tracker, ready, lines.length, subtotal, itemCount]);

  useEffect(() => {
    // `placing` suppresses the guard during checkout: placing an order empties
    // the cart on purpose, and without this the "empty cart" redirect races the
    // push to the confirmation page and wins.
    if (!ready || !shippingLoaded || placing) return;
    if (lines.length === 0) {
      router.replace('/cart');
    } else if (shipping === null) {
      // Arriving here without an address means the step was genuinely skipped.
      router.replace('/checkout/shipping');
    }
  }, [ready, shippingLoaded, placing, lines.length, shipping, router]);

  if (!ready || !shippingLoaded || (lines.length === 0 && !placing)) return null;

  async function placeOrder() {
    setPlacing(true);
    const orderId = newOrderId();
    const total = orderTotal(subtotal);

    tracker.track('purchase', {
      price: total,
      quantity: itemCount,
      properties: {
        order_id: orderId,
        subtotal,
        shipping: shippingFor(subtotal),
        line_count: lines.length,
        payment_method: 'mock_card',
      },
    });

    saveOrder({
      orderId,
      subtotal,
      shipping: shippingFor(subtotal),
      total,
      itemCount,
      email: shipping?.email ?? '',
      placedAt: new Date().toISOString(),
    });

    // Make sure the purchase event is on its way before the cart disappears.
    await tracker.flush();
    clear();
    clearCheckout();
    router.push('/checkout/confirm');
  }

  return (
    <div className="space-y-8">
      <CheckoutSteps current="payment" />
      <h1 className="text-2xl font-semibold tracking-tight">Payment</h1>

      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <div
            role="note"
            className="border-clay/30 bg-clay/10 flex items-start gap-3 rounded-lg border p-4 text-sm"
          >
            <ShieldCheck aria-hidden className="text-clay mt-0.5 h-4 w-4 shrink-0" />
            <p>
              <strong className="font-semibold">This is a mock payment step.</strong> No card
              details are collected anywhere in this demo, nothing is charged, and no order is
              placed. The button below only records the purchase event that the funnel measures.
            </p>
          </div>

          <fieldset className="border-border bg-surface rounded-lg border p-5">
            <legend className="px-2 text-sm font-medium">Payment method</legend>
            <div className="flex items-center gap-3">
              <span
                aria-hidden
                className="bg-surface-raised text-muted-foreground grid h-9 w-14 place-items-center rounded text-[10px] font-semibold tracking-wide"
              >
                MOCK
              </span>
              <div className="text-sm">
                <p className="font-medium">Demo card ending 4242</p>
                <p className="text-muted-foreground text-xs">Not a real payment method</p>
              </div>
            </div>
          </fieldset>

          {shipping && (
            <section className="border-border bg-surface rounded-lg border p-5 text-sm">
              <h2 className="font-medium">Delivering to</h2>
              <address className="text-muted-foreground mt-2 not-italic">
                {shipping.fullName}
                <br />
                {shipping.address1}
                {shipping.address2 && (
                  <>
                    <br />
                    {shipping.address2}
                  </>
                )}
                <br />
                {shipping.city}, {shipping.postcode}
                <br />
                {shipping.country}
              </address>
              <button
                type="button"
                className="text-primary mt-3 text-xs hover:underline"
                onClick={() => router.push('/checkout/shipping')}
              >
                Change delivery address
              </button>
            </section>
          )}

          <Button size="lg" className="w-full sm:w-auto" disabled={placing} onClick={placeOrder}>
            <Lock aria-hidden className="h-4 w-4" />
            {placing ? 'Placing order…' : `Place order (mock)`}
          </Button>
        </div>

        <OrderSummary subtotal={subtotal} itemCount={itemCount} showShippingHint={false} />
      </div>
    </div>
  );
}
