import { formatCurrency } from '@/lib/utils';

export function Price({
  value,
  currency = 'GBP',
  className,
}: {
  value: number;
  currency?: string;
  className?: string;
}) {
  return (
    <span className={className} data-testid="price">
      {formatCurrency(value, currency)}
    </span>
  );
}
