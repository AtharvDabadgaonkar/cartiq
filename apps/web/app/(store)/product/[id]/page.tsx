import { ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { AddToCartButton } from '@/components/store/add-to-cart-button';
import { Price } from '@/components/store/price';
import { ProductGrid } from '@/components/store/product-grid';
import { ProductImage } from '@/components/store/product-image';
import { ProductViewTracker } from '@/components/store/product-view-tracker';
import { Badge } from '@/components/ui/badge';
import { categoryLabel, getProduct, getRelatedProducts } from '@/lib/catalog';

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const product = await getProduct(decodeURIComponent(id));
  return { title: product?.title ?? 'Product' };
}

/** Renders the derived attributes, marked as derived where they are. */
function AttributeList({
  attributes,
  generatedFields,
}: {
  attributes: Record<string, string | number | string[]>;
  generatedFields: string[];
}) {
  const entries = Object.entries(attributes);
  if (entries.length === 0) return null;

  return (
    <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
      {entries.map(([key, value]) => {
        const derived = generatedFields.includes(`attributes.${key}`);
        return (
          <div key={key}>
            <dt className="text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</dt>
            <dd className="mt-0.5 flex items-center gap-1.5 font-medium">
              {Array.isArray(value) ? value.join(', ') : String(value)}
              {derived && (
                <span
                  className="text-muted-foreground text-[10px] font-normal"
                  title="Derived from the product description by CartIQ, not present in the source data"
                >
                  derived
                </span>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export default async function ProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const product = await getProduct(decodeURIComponent(id));
  if (!product) notFound();

  const related = await getRelatedProducts(product);

  return (
    <div className="space-y-12">
      <ProductViewTracker
        productId={product.id}
        price={product.price}
        categoryPath={product.categoryPath}
      />

      <nav aria-label="Breadcrumb" className="text-muted-foreground text-sm">
        <ol className="flex flex-wrap items-center gap-1">
          <li>
            <Link href="/" className="hover:text-foreground hover:underline">
              Shop
            </Link>
          </li>
          <ChevronRight aria-hidden className="h-3 w-3" />
          <li>
            <Link
              href={`/category/${encodeURIComponent(product.categoryPath)}`}
              className="hover:text-foreground hover:underline"
            >
              {categoryLabel(product.categoryPath)}
            </Link>
          </li>
          <ChevronRight aria-hidden className="h-3 w-3" />
          <li aria-current="page" className="text-foreground">
            {product.title}
          </li>
        </ol>
      </nav>

      <div className="grid gap-8 md:grid-cols-2">
        <ProductImage
          productId={product.id}
          title={product.title}
          size="detail"
          className="aspect-square w-full"
        />

        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{product.title}</h1>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Price
              value={product.price}
              currency={product.currency}
              className="text-2xl font-semibold"
            />
            {product.inStock ? (
              <Badge variant="moss">In stock</Badge>
            ) : (
              <Badge variant="clay">Out of stock</Badge>
            )}
            {product.unitsSold > 0 && (
              <Badge variant="neutral">{product.unitsSold.toLocaleString('en-GB')} sold</Badge>
            )}
          </div>

          <p className="text-muted-foreground mt-4 text-sm">
            {product.description ?? (
              <>
                This product has no description in the source data. Catalog Readiness (Phase 8)
                scores exactly this kind of gap, because an AI shopping agent cannot match a product
                it cannot read.
              </>
            )}
          </p>

          <AttributeList
            attributes={product.attributes}
            generatedFields={product.generatedFields}
          />

          <dl className="border-border mt-6 grid grid-cols-2 gap-x-6 gap-y-3 border-t pt-6 text-sm">
            <div>
              <dt className="text-muted-foreground">Product code</dt>
              <dd className="mt-0.5 font-mono text-xs">{product.id}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Brand</dt>
              <dd className="text-muted-foreground mt-0.5">not in source data</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">GTIN</dt>
              <dd className="text-muted-foreground mt-0.5">not in source data</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Category</dt>
              <dd className="mt-0.5">
                {categoryLabel(product.categoryPath)}{' '}
                <span className="text-muted-foreground text-[10px]" title="Derived by CartIQ">
                  derived
                </span>
              </dd>
            </div>
          </dl>

          <AddToCartButton
            productId={product.id}
            title={product.title}
            price={product.price}
            size="lg"
            className="mt-8 w-full sm:w-auto"
          />
        </div>
      </div>

      {related.length > 0 && (
        <section aria-labelledby="related-heading">
          <h2
            id="related-heading"
            className="text-muted-foreground text-sm font-semibold uppercase tracking-widest"
          >
            More in {categoryLabel(product.categoryPath)}
          </h2>
          <p className="text-muted-foreground mt-1 text-xs">
            Same category, nearest price. Personalised recommendations arrive in Phase 6.
          </p>
          <div className="mt-4">
            <ProductGrid products={related} listName="related" />
          </div>
        </section>
      )}
    </div>
  );
}
