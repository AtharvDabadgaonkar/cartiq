'use client';

import { useEffect, useRef } from 'react';
import { useTracker } from '@/components/providers/tracking-provider';

/** Emits `product_view` once per product per mount. */
export function ProductViewTracker({
  productId,
  price,
  categoryPath,
}: {
  productId: string;
  price: number;
  categoryPath: string;
}) {
  const tracker = useTracker();
  const seen = useRef<string | null>(null);

  useEffect(() => {
    if (seen.current === productId) return;
    seen.current = productId;
    tracker.track('product_view', {
      product_id: productId,
      price,
      properties: { category_path: categoryPath },
    });
  }, [tracker, productId, price, categoryPath]);

  return null;
}
