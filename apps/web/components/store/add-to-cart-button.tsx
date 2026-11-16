'use client';

import { Check, ShoppingCart } from 'lucide-react';
import { useState } from 'react';
import { useCart } from '@/components/providers/cart-provider';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/** Adding to cart is the single most important tracked action in the funnel. */
export function AddToCartButton({
  productId,
  title,
  price,
  quantity = 1,
  size = 'md',
  className,
}: {
  productId: string;
  title: string;
  price: number;
  quantity?: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}) {
  const { addItem } = useCart();
  const [added, setAdded] = useState(false);

  return (
    <>
      <Button
        size={size}
        className={cn(className)}
        onClick={() => {
          addItem({ productId, title, price, quantity });
          setAdded(true);
          window.setTimeout(() => setAdded(false), 1800);
        }}
      >
        {added ? (
          <Check aria-hidden className="h-4 w-4" />
        ) : (
          <ShoppingCart aria-hidden className="h-4 w-4" />
        )}
        {added ? 'Added' : 'Add to cart'}
        <span className="sr-only"> — {title}</span>
      </Button>
      {/* Announced to screen readers without stealing focus. */}
      <span role="status" aria-live="polite" className="sr-only">
        {added ? `${title} added to cart` : ''}
      </span>
    </>
  );
}
