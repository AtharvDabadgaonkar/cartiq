'use client';

import { Minus, Plus, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCart } from '@/components/providers/cart-provider';
import { useTracker } from '@/components/providers/tracking-provider';
import { OrderSummary } from '@/components/store/order-summary';
import { Price } from '@/components/store/price';
import { ProductImage } from '@/components/store/product-image';
import { Button } from '@/components/ui/button';
import { buttonVariants } from '@/components/ui/button-variants';

export function CartView() {
  const { lines, itemCount, subtotal, ready, setQuantity, removeItem } = useCart();
  const tracker = useTracker();
  const router = useRouter();

  if (!ready) {
    return <p className="text-muted-foreground py-12 text-center text-sm">Loading your cart…</p>;
  }

  if (lines.length === 0) {
    return (
      <div className="py-16 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Your cart is empty</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          Nothing here yet. Have a look at what is selling.
        </p>
        <Link href="/" className={`mt-6 inline-flex ${buttonVariants({ size: 'lg' })}`}>
          Browse the shop
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Your cart</h1>

      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <ul className="divide-border border-border divide-y rounded-lg border">
          {lines.map((line) => (
            <li key={line.productId} className="flex gap-4 p-4">
              <ProductImage
                productId={line.productId}
                title={line.title}
                size="line"
                className="h-20 w-20 shrink-0"
              />

              <div className="min-w-0 flex-1">
                <Link
                  href={`/product/${encodeURIComponent(line.productId)}`}
                  className="hover:text-primary line-clamp-2 text-sm font-medium hover:underline"
                >
                  {line.title}
                </Link>
                <p className="text-muted-foreground mt-1 text-xs">
                  <Price value={line.price} /> each
                </p>

                <div className="mt-3 flex items-center gap-2">
                  <div className="border-border flex items-center rounded-md border">
                    <button
                      type="button"
                      className="hover:bg-surface-raised grid h-8 w-8 place-items-center rounded-l-md"
                      aria-label={`Decrease quantity of ${line.title}`}
                      onClick={() => setQuantity(line.productId, line.quantity - 1)}
                    >
                      <Minus aria-hidden className="h-3.5 w-3.5" />
                    </button>
                    <span
                      className="w-10 text-center text-sm tabular-nums"
                      aria-label={`Quantity of ${line.title}`}
                    >
                      {line.quantity}
                    </span>
                    <button
                      type="button"
                      className="hover:bg-surface-raised grid h-8 w-8 place-items-center rounded-r-md"
                      aria-label={`Increase quantity of ${line.title}`}
                      onClick={() => setQuantity(line.productId, line.quantity + 1)}
                    >
                      <Plus aria-hidden className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  <button
                    type="button"
                    className="text-muted-foreground hover:bg-surface-raised hover:text-clay inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs"
                    onClick={() => removeItem(line.productId)}
                  >
                    <Trash2 aria-hidden className="h-3.5 w-3.5" />
                    Remove<span className="sr-only"> {line.title}</span>
                  </button>
                </div>
              </div>

              <Price value={line.price * line.quantity} className="text-sm font-semibold" />
            </li>
          ))}
        </ul>

        <div className="space-y-4">
          <OrderSummary subtotal={subtotal} itemCount={itemCount} />
          <Button
            size="lg"
            className="w-full"
            onClick={() => {
              // The funnel's checkout_start: the moment the shopper commits to buying.
              tracker.track('checkout_start', {
                price: subtotal,
                quantity: itemCount,
                properties: { line_count: lines.length },
              });
              router.push('/checkout/shipping');
            }}
          >
            Proceed to checkout
          </Button>
          <p className="text-muted-foreground text-center text-xs">
            Demo checkout. No payment is taken and no order is placed.
          </p>
        </div>
      </div>
    </div>
  );
}
