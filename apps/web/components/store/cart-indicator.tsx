'use client';

import { ShoppingBag } from 'lucide-react';
import Link from 'next/link';
import { useCart } from '@/components/providers/cart-provider';

export function CartIndicator() {
  const { itemCount, ready } = useCart();

  return (
    <Link
      href="/cart"
      className="hover:bg-surface-raised relative inline-flex h-10 items-center gap-2 rounded-md px-3 text-sm"
      aria-label={ready ? `Cart, ${itemCount} ${itemCount === 1 ? 'item' : 'items'}` : 'Cart'}
    >
      <ShoppingBag aria-hidden className="h-4 w-4" />
      <span className="hidden sm:inline">Cart</span>
      {ready && itemCount > 0 && (
        <span
          aria-hidden
          className="bg-primary text-primary-foreground grid h-5 min-w-5 place-items-center rounded-full px-1 text-xs font-semibold"
        >
          {itemCount}
        </span>
      )}
    </Link>
  );
}
