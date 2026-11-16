'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { buttonVariants } from '@/components/ui/button-variants';
import { cn } from '@/lib/utils';

export function Pagination({
  page,
  pageSize,
  total,
}: {
  page: number;
  pageSize: number;
  total: number;
}) {
  const params = useSearchParams();
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  if (lastPage <= 1) return null;

  const href = (target: number) => {
    const next = new URLSearchParams(params?.toString());
    next.set('page', String(target));
    return `?${next.toString()}`;
  };

  const disabled = 'pointer-events-none opacity-40';

  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-3 pt-2">
      <Link
        href={href(page - 1)}
        aria-disabled={page <= 1}
        tabIndex={page <= 1 ? -1 : undefined}
        className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), page <= 1 && disabled)}
      >
        <ChevronLeft aria-hidden className="h-4 w-4" /> Previous
      </Link>
      <span className="text-muted-foreground text-sm" aria-current="page">
        Page {page} of {lastPage}
      </span>
      <Link
        href={href(page + 1)}
        aria-disabled={page >= lastPage}
        tabIndex={page >= lastPage ? -1 : undefined}
        className={cn(
          buttonVariants({ variant: 'outline', size: 'sm' }),
          page >= lastPage && disabled,
        )}
      >
        Next <ChevronRight aria-hidden className="h-4 w-4" />
      </Link>
    </nav>
  );
}
