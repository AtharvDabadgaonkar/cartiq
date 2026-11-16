import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { ProductGrid } from '@/components/store/product-grid';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button-variants';
import { listCategories, listProducts } from '@/lib/catalog';

export const metadata = { title: 'Shop' };

export default async function StoreHomePage() {
  const [{ products: bestSellers }, { products: newIn }, categories] = await Promise.all([
    listProducts({ sort: 'popular', pageSize: 8 }),
    listProducts({ sort: 'price_asc', pageSize: 4, minPrice: 5 }),
    listCategories(),
  ]);

  return (
    <div className="space-y-12">
      <section className="ember-glow -mx-4 rounded-lg px-4 py-10 sm:-mx-6 sm:px-6">
        <Badge variant="amber">Demo storefront</Badge>
        <h1 className="mt-4 max-w-2xl text-balance text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
          Giftware, homeware and seasonal pieces — from a real retail catalog.
        </h1>
        <p className="text-muted-foreground mt-3 max-w-xl">
          Every product, title and price here comes from two years of real transactions. Browse it,
          fill a cart, and check out; nothing is charged and no order is placed.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/search?q=christmas" className={buttonVariants({ size: 'lg' })}>
            Shop seasonal <ArrowRight aria-hidden className="h-4 w-4" />
          </Link>
          <Link href="/about" className={buttonVariants({ size: 'lg', variant: 'outline' })}>
            How this was built
          </Link>
        </div>
      </section>

      <section aria-labelledby="categories-heading">
        <h2
          id="categories-heading"
          className="text-muted-foreground text-sm font-semibold uppercase tracking-widest"
        >
          Shop by category
        </h2>
        <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {categories.slice(0, 8).map((category) => (
            <li key={category.path}>
              <Link
                href={`/category/${encodeURIComponent(category.path)}`}
                className="border-border bg-surface hover:border-primary/40 flex h-full flex-col justify-between rounded-lg border p-4 transition-colors"
              >
                <span className="font-medium">{category.label}</span>
                <span className="text-muted-foreground mt-2 text-xs">
                  {category.productCount.toLocaleString('en-GB')} products
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="bestsellers-heading">
        <div className="flex items-end justify-between gap-4">
          <h2
            id="bestsellers-heading"
            className="text-muted-foreground text-sm font-semibold uppercase tracking-widest"
          >
            Best selling
          </h2>
          <Link href="/search?sort=popular" className="text-primary text-sm hover:underline">
            See all
          </Link>
        </div>
        <div className="mt-4">
          <ProductGrid products={bestSellers} listName="home_bestsellers" />
        </div>
      </section>

      <section aria-labelledby="picks-heading">
        <h2
          id="picks-heading"
          className="text-muted-foreground text-sm font-semibold uppercase tracking-widest"
        >
          Under £10
        </h2>
        <div className="mt-4">
          <ProductGrid products={newIn} listName="home_value" />
        </div>
      </section>
    </div>
  );
}
