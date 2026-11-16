/**
 * Catalog types and pure helpers.
 *
 * Separate from `lib/catalog.ts` on purpose: that module talks to Prisma and is
 * server-only, so anything a client component needs has to live here. Importing
 * a value from the server module into a client component pulls Prisma into the
 * browser bundle, which fails at runtime rather than at build time.
 */

export interface CatalogProduct {
  id: string;
  title: string;
  description: string | null;
  brand: string | null;
  category: string;
  categoryPath: string;
  price: number;
  currency: string;
  imageUrl: string | null;
  gtin: string | null;
  inStock: boolean;
  attributes: Record<string, string | number | string[]>;
  /** Fields derived by CartIQ rather than present in the source data. */
  generatedFields: string[];
  unitsSold: number;
}

export interface CategorySummary {
  path: string;
  label: string;
  productCount: number;
}

export type SortKey = 'popular' | 'price_asc' | 'price_desc' | 'title';

export const PAGE_SIZE = 24;

/** "home.decor" -> "Home · Decor" */
export function categoryLabel(path: string): string {
  return path
    .split('.')
    .map((part) => part.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()))
    .join(' · ');
}
