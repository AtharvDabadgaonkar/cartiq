import { ProductGrid } from '@/components/store/product-grid';
import { SearchResultsTracker } from '@/components/store/search-results-tracker';
import { listProducts, type SortKey } from '@/lib/catalog';
import { Pagination } from '@/components/store/pagination';
import { SortSelect } from '@/components/store/sort-select';

export const metadata = { title: 'Search' };

const SORTS: SortKey[] = ['popular', 'price_asc', 'price_desc', 'title'];

function toNumber(value: string | undefined): number | undefined {
  if (value === undefined) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const first = (key: string) => {
    const value = params[key];
    return Array.isArray(value) ? value[0] : value;
  };

  const query = first('q')?.trim() ?? '';
  const sortParam = first('sort');
  const sort = SORTS.includes(sortParam as SortKey) ? (sortParam as SortKey) : 'popular';
  const page = Math.max(1, Number(first('page') ?? 1) || 1);

  const { products, total, pageSize } = await listProducts({
    search: query || undefined,
    minPrice: toNumber(first('min')),
    maxPrice: toNumber(first('max')),
    sort,
    page,
  });

  return (
    <div className="space-y-6">
      {/* Emits the `search` event for results arrived at by URL, not just by
          typing in the header box. */}
      <SearchResultsTracker query={query} resultCount={total} />

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {query ? `Results for “${query}”` : 'All products'}
          </h1>
          <p className="text-muted-foreground mt-1 text-sm" aria-live="polite">
            {total.toLocaleString('en-GB')} {total === 1 ? 'product' : 'products'}
          </p>
        </div>
        <SortSelect value={sort} />
      </div>

      <ProductGrid
        products={products}
        listName="search"
        emptyMessage={
          query
            ? `Nothing matched “${query}”. Try a shorter or more general term.`
            : 'No products match those filters.'
        }
      />

      <Pagination page={page} pageSize={pageSize} total={total} />
    </div>
  );
}
