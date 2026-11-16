'use client';

import Link from 'next/link';
import { useTracker } from '@/components/providers/tracking-provider';
import { AddToCartButton } from '@/components/store/add-to-cart-button';
import { Price } from '@/components/store/price';
import { ProductImage } from '@/components/store/product-image';
import { Badge } from '@/components/ui/badge';
import type { CatalogProduct } from '@/lib/catalog-shared';
import { categoryLabel } from '@/lib/catalog-shared';

export function ProductCard({
  product,
  position,
  listName,
}: {
  product: CatalogProduct;
  /** 1-based position in the list, for click-through analysis. */
  position?: number;
  /** Which list this card appeared in, e.g. "search" or "related". */
  listName?: string;
}) {
  const tracker = useTracker();

  return (
    <article className="border-border bg-surface hover:border-primary/40 group flex flex-col rounded-lg border p-3 transition-colors">
      <Link
        href={`/product/${encodeURIComponent(product.id)}`}
        className="rounded-md focus-visible:ring-2"
        onClick={() =>
          tracker.track('recommendation_click', {
            product_id: product.id,
            price: product.price,
            properties: {
              ...(listName ? { list: listName } : {}),
              ...(position ? { position } : {}),
            },
          })
        }
      >
        <ProductImage
          productId={product.id}
          title={product.title}
          className="aspect-square w-full"
        />
        <h3 className="group-hover:text-primary mt-3 line-clamp-2 text-sm font-medium leading-snug">
          {product.title}
        </h3>
      </Link>

      <p className="text-muted-foreground mt-1 text-xs">{categoryLabel(product.categoryPath)}</p>

      <div className="mt-2 flex items-center justify-between gap-2">
        <Price value={product.price} currency={product.currency} className="font-semibold" />
        {product.unitsSold > 0 && (
          <Badge variant="neutral" title="Units sold across the loaded data">
            {product.unitsSold.toLocaleString('en-GB')} sold
          </Badge>
        )}
      </div>

      <AddToCartButton
        productId={product.id}
        title={product.title}
        price={product.price}
        size="sm"
        className="mt-3 w-full"
      />
    </article>
  );
}
