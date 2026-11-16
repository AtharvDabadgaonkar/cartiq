import 'server-only';

import { Prisma } from '@prisma/client';
import { prisma } from '@/lib/db';
import {
  PAGE_SIZE,
  categoryLabel,
  type CatalogProduct,
  type CategorySummary,
  type SortKey,
} from '@/lib/catalog-shared';

/**
 * Storefront catalog queries.
 *
 * Server-only (`import 'server-only'` makes that a build error rather than a
 * runtime one). Popularity comes from `int_product_popularity` (models/), so the
 * storefront and the console share one definition of "best selling" rather than
 * each inventing their own.
 */

export { PAGE_SIZE, categoryLabel } from '@/lib/catalog-shared';
export type { CatalogProduct, CategorySummary, SortKey } from '@/lib/catalog-shared';

export interface ProductQuery {
  search?: string;
  categoryPath?: string;
  minPrice?: number;
  maxPrice?: number;
  sort?: SortKey;
  page?: number;
  pageSize?: number;
}

interface ProductRow {
  id: string;
  title: string;
  description: string | null;
  brand: string | null;
  category: string;
  category_path: string;
  price: Prisma.Decimal;
  currency: string;
  image_url: string | null;
  gtin: string | null;
  in_stock: boolean;
  attributes: Record<string, string | number | string[]>;
  generated_fields: string[];
  units_sold: bigint;
}

function toProduct(row: ProductRow): CatalogProduct {
  return {
    id: row.id,
    title: row.title,
    description: row.description,
    brand: row.brand,
    category: row.category,
    categoryPath: row.category_path,
    price: Number(row.price),
    currency: row.currency,
    imageUrl: row.image_url,
    gtin: row.gtin,
    inStock: row.in_stock,
    attributes: row.attributes ?? {},
    generatedFields: row.generated_fields ?? [],
    unitsSold: Number(row.units_sold ?? 0),
  };
}

const SORTS: Record<SortKey, Prisma.Sql> = {
  popular: Prisma.sql`pop.units_sold DESC, p.title ASC`,
  price_asc: Prisma.sql`p.price ASC, p.title ASC`,
  price_desc: Prisma.sql`p.price DESC, p.title ASC`,
  title: Prisma.sql`p.title ASC`,
};

/**
 * Builds the WHERE clause shared by the listing and its count.
 * Search matches every term against the title, so "blue glass" narrows rather
 * than widens — the behaviour a shopper expects from a search box.
 */
function whereClause(query: ProductQuery): Prisma.Sql {
  const conditions: Prisma.Sql[] = [Prisma.sql`TRUE`];

  if (query.search?.trim()) {
    for (const term of query.search.trim().split(/\s+/).slice(0, 8)) {
      conditions.push(Prisma.sql`p.title ILIKE ${`%${term}%`}`);
    }
  }
  if (query.categoryPath) {
    conditions.push(Prisma.sql`p.category_path = ${query.categoryPath}`);
  }
  if (query.minPrice !== undefined) {
    conditions.push(Prisma.sql`p.price >= ${query.minPrice}`);
  }
  if (query.maxPrice !== undefined) {
    conditions.push(Prisma.sql`p.price <= ${query.maxPrice}`);
  }

  return Prisma.join(conditions, ' AND ');
}

export async function listProducts(
  query: ProductQuery = {},
): Promise<{ products: CatalogProduct[]; total: number; page: number; pageSize: number }> {
  const pageSize = query.pageSize ?? PAGE_SIZE;
  const page = Math.max(1, query.page ?? 1);
  const where = whereClause(query);
  const order = SORTS[query.sort ?? 'popular'];

  const [rows, counted] = await Promise.all([
    prisma.$queryRaw<ProductRow[]>`
      SELECT p.*, COALESCE(pop.units_sold, 0) AS units_sold
      FROM products p
      LEFT JOIN int_product_popularity pop ON pop.product_id = p.id
      WHERE ${where}
      ORDER BY ${order}
      LIMIT ${pageSize} OFFSET ${(page - 1) * pageSize}
    `,
    prisma.$queryRaw<{ count: bigint }[]>`
      SELECT COUNT(*) AS count FROM products p WHERE ${where}
    `,
  ]);

  return {
    products: rows.map(toProduct),
    total: Number(counted[0]?.count ?? 0),
    page,
    pageSize,
  };
}

export async function getProduct(id: string): Promise<CatalogProduct | null> {
  const rows = await prisma.$queryRaw<ProductRow[]>`
    SELECT p.*, COALESCE(pop.units_sold, 0) AS units_sold
    FROM products p
    LEFT JOIN int_product_popularity pop ON pop.product_id = p.id
    WHERE p.id = ${id}
    LIMIT 1
  `;
  return rows[0] ? toProduct(rows[0]) : null;
}

/** Several products in one round trip, for the cart and the order summary. */
export async function getProductsByIds(ids: string[]): Promise<CatalogProduct[]> {
  if (ids.length === 0) return [];
  const rows = await prisma.$queryRaw<ProductRow[]>`
    SELECT p.*, COALESCE(pop.units_sold, 0) AS units_sold
    FROM products p
    LEFT JOIN int_product_popularity pop ON pop.product_id = p.id
    WHERE p.id IN (${Prisma.join(ids.slice(0, 100))})
  `;
  return rows.map(toProduct);
}

/**
 * Same category, nearest price. Deliberately simple and explainable: real
 * co-occurrence recommendations are Module 4 (Phase 6), and labelling this as
 * "personalised" before then would overstate it.
 */
export async function getRelatedProducts(
  product: CatalogProduct,
  limit = 4,
): Promise<CatalogProduct[]> {
  const rows = await prisma.$queryRaw<ProductRow[]>`
    SELECT p.*, COALESCE(pop.units_sold, 0) AS units_sold
    FROM products p
    LEFT JOIN int_product_popularity pop ON pop.product_id = p.id
    WHERE p.category_path = ${product.categoryPath}
      AND p.id <> ${product.id}
    ORDER BY ABS(p.price - ${product.price}::numeric) ASC, pop.units_sold DESC
    LIMIT ${limit}
  `;
  return rows.map(toProduct);
}

export async function listCategories(): Promise<CategorySummary[]> {
  const rows = await prisma.$queryRaw<{ category_path: string; count: bigint }[]>`
    SELECT category_path, COUNT(*) AS count
    FROM products
    GROUP BY category_path
    ORDER BY count DESC
  `;
  return rows.map((row) => ({
    path: row.category_path,
    label: categoryLabel(row.category_path),
    productCount: Number(row.count),
  }));
}

/** Price bounds, so the filter UI reflects the catalog instead of guessing. */
export async function getPriceRange(): Promise<{ min: number; max: number }> {
  const rows = await prisma.$queryRaw<{ min: Prisma.Decimal; max: Prisma.Decimal }[]>`
    SELECT MIN(price) AS min, MAX(price) AS max FROM products
  `;
  return { min: Number(rows[0]?.min ?? 0), max: Number(rows[0]?.max ?? 0) };
}
