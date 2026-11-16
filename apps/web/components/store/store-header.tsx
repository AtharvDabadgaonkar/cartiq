import Link from 'next/link';
import { Suspense } from 'react';
import { CartIndicator } from '@/components/store/cart-indicator';
import { SearchBar } from '@/components/store/search-bar';
import { ThemeToggle } from '@/components/theme-toggle';
import type { CategorySummary } from '@/lib/catalog-shared';

export function StoreHeader({ categories }: { categories: CategorySummary[] }) {
  return (
    <header className="border-border bg-background/95 sticky top-0 z-40 border-b backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 rounded-md font-semibold tracking-tight">
          <span className="bg-primary text-primary-foreground grid h-7 w-7 place-items-center rounded-md text-sm font-bold">
            C
          </span>
          CartIQ
          <span className="sr-only">home</span>
        </Link>

        <div className="order-last w-full sm:order-none sm:w-auto sm:flex-1">
          <Suspense fallback={<div className="h-10" />}>
            <SearchBar />
          </Suspense>
        </div>

        <nav aria-label="Main" className="flex items-center gap-1">
          <Link
            href="/about"
            className="text-muted-foreground hover:bg-surface-raised hover:text-foreground hidden rounded-md px-3 py-2 text-sm md:inline-block"
          >
            About this project
          </Link>
          <CartIndicator />
          <ThemeToggle />
        </nav>
      </div>

      <nav aria-label="Categories" className="border-border border-t">
        <ul className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 py-2 sm:px-6">
          {categories.slice(0, 10).map((category) => (
            <li key={category.path}>
              <Link
                href={`/category/${encodeURIComponent(category.path)}`}
                className="text-muted-foreground hover:bg-surface-raised hover:text-foreground inline-block whitespace-nowrap rounded-md px-3 py-1.5 text-sm"
              >
                {category.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
