import { Price } from '@/components/store/price';
import { FREE_SHIPPING_THRESHOLD, amountToFreeShipping, shippingFor } from '@/lib/store/shipping';
import { formatCurrency } from '@/lib/utils';

export function OrderSummary({
  subtotal,
  itemCount,
  showShippingHint = true,
}: {
  subtotal: number;
  itemCount: number;
  showShippingHint?: boolean;
}) {
  const shipping = shippingFor(subtotal);
  const remaining = amountToFreeShipping(subtotal);
  const total = Math.round((subtotal + shipping) * 100) / 100;

  return (
    <div className="border-border bg-surface rounded-lg border p-5">
      <h2 className="text-muted-foreground text-sm font-semibold uppercase tracking-widest">
        Order summary
      </h2>
      <dl className="mt-4 space-y-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">
            Subtotal ({itemCount} {itemCount === 1 ? 'item' : 'items'})
          </dt>
          <dd>
            <Price value={subtotal} />
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Shipping</dt>
          <dd>{shipping === 0 ? 'Free' : <Price value={shipping} />}</dd>
        </div>
        <div className="border-border flex justify-between border-t pt-2 text-base font-semibold">
          <dt>Total</dt>
          <dd>
            <Price value={total} />
          </dd>
        </div>
      </dl>

      {showShippingHint && remaining > 0 && subtotal > 0 && (
        <p className="bg-surface-raised text-muted-foreground mt-4 rounded-md px-3 py-2 text-xs">
          Spend {formatCurrency(remaining)} more for free delivery (orders over{' '}
          {formatCurrency(FREE_SHIPPING_THRESHOLD)}).
        </p>
      )}
    </div>
  );
}
