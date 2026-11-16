import { ProductCard } from '@/components/store/product-card';
import type { CatalogProduct } from '@/lib/catalog-shared';

export function ProductGrid({
  products,
  listName,
  emptyMessage = 'No products match that.',
}: {
  products: CatalogProduct[];
  listName?: string;
  emptyMessage?: string;
}) {
  if (products.length === 0) {
    return (
      <p className="border-border text-muted-foreground rounded-lg border border-dashed px-6 py-12 text-center text-sm">
        {emptyMessage}
      </p>
    );
  }

  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {products.map((product, index) => (
        <li key={product.id}>
          <ProductCard product={product} position={index + 1} listName={listName} />
        </li>
      ))}
    </ul>
  );
}
