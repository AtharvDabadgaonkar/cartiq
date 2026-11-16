'use client';

import { CheckCircle2 } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { CheckoutSteps } from '@/components/store/checkout-steps';
import { Price } from '@/components/store/price';
import { buttonVariants } from '@/components/ui/button-variants';
import { readOrder, type PlacedOrder } from '@/lib/store/checkout';

export function ConfirmStep() {
  const [order, setOrder] = useState<PlacedOrder | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setOrder(readOrder());
    setLoaded(true);
  }, []);

  if (!loaded) return null;

  if (!order) {
    return (
      <div className="py-16 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">No recent order</h1>
        <p className="text-muted-foreground mt-2 text-sm">Nothing was placed in this session.</p>
        <Link href="/" className={`mt-6 inline-flex ${buttonVariants({ size: 'lg' })}`}>
          Back to the shop
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <CheckoutSteps current="confirm" />

      <div className="border-moss/30 bg-moss/10 rounded-lg border p-6">
        <div className="flex items-start gap-3">
          <CheckCircle2 aria-hidden className="text-moss mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Order confirmed</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Reference <span className="font-mono">{order.orderId}</span>
              {order.email && <> · a confirmation would go to {order.email}</>}
            </p>
          </div>
        </div>
      </div>

      <div className="border-border bg-surface rounded-lg border p-5">
        <h2 className="text-muted-foreground text-sm font-semibold uppercase tracking-widest">
          What was recorded
        </h2>
        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Items</dt>
            <dd>{order.itemCount}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Subtotal</dt>
            <dd>
              <Price value={order.subtotal} />
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Shipping</dt>
            <dd>{order.shipping === 0 ? 'Free' : <Price value={order.shipping} />}</dd>
          </div>
          <div className="border-border flex justify-between border-t pt-2 font-semibold">
            <dt>Total</dt>
            <dd>
              <Price value={order.total} />
            </dd>
          </div>
        </dl>
      </div>

      <div
        role="note"
        className="border-border bg-surface-raised text-muted-foreground rounded-lg border p-5 text-sm"
      >
        <p>
          <strong className="text-foreground font-semibold">Nothing was actually bought.</strong> No
          payment was taken, no address was stored on a server, and no order exists. What this step
          did produce is a <code className="font-mono text-xs">purchase</code> event, which is the
          last step of the funnel the console measures.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <Link href="/" className={buttonVariants({ size: 'lg' })}>
          Keep shopping
        </Link>
        <Link href="/console" className={buttonVariants({ size: 'lg', variant: 'outline' })}>
          See how it is measured
        </Link>
      </div>
    </div>
  );
}
