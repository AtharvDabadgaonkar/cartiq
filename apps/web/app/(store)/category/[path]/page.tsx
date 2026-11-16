import { notFound } from 'next/navigation';
import { Pagination } from '@/components/store/pagination';
import { ProductGrid } from '@/components/store/product-grid';
import { SortSelect } from '@/components/store/sort-select';
import { categoryLabel, listCategories, listProducts, type SortKey } from '@/lib/catalog';

const SORTS: SortKey[] = ['popular', 'price_asc', 'price_desc', 'title'];

export async function generateMetadata({ params }: { params: Promise<{ path: string }> }) {
  const { path } = await params;
  return { title: categoryLabel(decodeURIComponent(path)) };
}

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ path: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ path }, query] = await Promise.all([params, searchParams]);
  const categoryPath = decodeURIComponent(path);

  const categories = await listCategories();
  if (!categories.some((category) => category.path === categoryPath)) notFound();

  const first = (key: string) => {
    const value = query[key];
    return Array.isArray(value) ? value[0] : value;
  };
  const sortParam = first('sort');
  const sort = SORTS.includes(sortParam as SortKey) ? (sortParam as SortKey) : 'popular';
  const page = Math.max(1, Number(first('page') ?? 1) || 1);

  const { products, total, pageSize } = await listProducts({ categoryPath, sort, page });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{categoryLabel(categoryPath)}</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            {total.toLocaleString('en-GB')} {total === 1 ? 'product' : 'products'}
            {categoryPath === 'uncategorised' && (
              <>
                {' '}
                · no category rule matched these, so they are left uncategorised rather than forced
                into a bucket
              </>
            )}
          </p>
        </div>
        <SortSelect value={sort} />
      </div>

      <ProductGrid products={products} listName={`category:${categoryPath}`} />
      <Pagination page={page} pageSize={pageSize} total={total} />
    </div>
  );
}
