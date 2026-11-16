import { cn } from '@/lib/utils';

/**
 * The source dataset has no product imagery at all, so there is nothing to
 * show. Rather than pull in a stock photo that misrepresents the product, this
 * renders a deterministic placeholder derived from the product id and says
 * plainly that no image exists — which is also the Module 6 finding.
 */

const PALETTE = [
  'from-primary/25 to-clay/15',
  'from-clay/25 to-plum/15',
  'from-moss/25 to-ochre/15',
  'from-plum/25 to-primary/15',
  'from-ochre/25 to-moss/15',
] as const;

function hash(input: string): number {
  let value = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    value ^= input.charCodeAt(i);
    value = Math.imul(value, 0x01000193) >>> 0;
  }
  return value >>> 0;
}

function initials(title: string): string {
  return title
    .split(/\s+/)
    .filter((word) => /[a-z]/i.test(word))
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('');
}

export function ProductImage({
  productId,
  title,
  className,
  size = 'card',
}: {
  productId: string;
  title: string;
  className?: string;
  size?: 'card' | 'detail' | 'line';
}) {
  const gradient = PALETTE[hash(productId) % PALETTE.length];
  const textSize = size === 'detail' ? 'text-5xl' : size === 'line' ? 'text-sm' : 'text-2xl';

  return (
    <div
      className={cn(
        'relative grid place-items-center overflow-hidden rounded-md bg-gradient-to-br',
        gradient,
        className,
      )}
      // Decorative: the product name is already the accessible label nearby.
      role="presentation"
      title="No product image in the source dataset"
    >
      <span className={cn('text-foreground/70 font-semibold tracking-tight', textSize)}>
        {initials(title) || '??'}
      </span>
      {size === 'detail' && (
        <span className="bg-background/70 text-muted-foreground absolute bottom-2 left-2 rounded px-1.5 py-0.5 text-[10px]">
          no image in source data
        </span>
      )}
    </div>
  );
}
