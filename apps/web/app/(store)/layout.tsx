import { Suspense } from 'react';
import { CartProvider } from '@/components/providers/cart-provider';
import { TrackingProvider } from '@/components/providers/tracking-provider';
import { DemoBanner } from '@/components/demo-banner';
import { StoreFooter } from '@/components/store/store-footer';
import { StoreHeader } from '@/components/store/store-header';
import { listCategories } from '@/lib/catalog';

/**
 * Storefront chrome. Tracking wraps the cart, because cart mutations emit
 * events and therefore need a tracker above them.
 */

/**
 * Rendered per request rather than prerendered. Two reasons: the catalog is
 * read from Postgres, so a build would otherwise need a live database (CI's web
 * job has none), and a demo store should reflect the data that is actually
 * loaded rather than whatever existed at build time.
 */
export const dynamic = 'force-dynamic';
export default async function StoreLayout({ children }: { children: React.ReactNode }) {
  const categories = await listCategories();

  return (
    <Suspense fallback={null}>
      <TrackingProvider>
        <CartProvider>
          <DemoBanner />
          <StoreHeader categories={categories} />
          <main id="main" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
            {children}
          </main>
          <StoreFooter />
        </CartProvider>
      </TrackingProvider>
    </Suspense>
  );
}
