'use client';

import { Search } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { useTracker } from '@/components/providers/tracking-provider';
import { cn } from '@/lib/utils';

export function SearchBar({
  className,
  autoFocus = false,
}: {
  className?: string;
  autoFocus?: boolean;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const tracker = useTracker();
  const [value, setValue] = useState(params?.get('q') ?? '');

  return (
    <form
      role="search"
      className={cn('relative flex-1', className)}
      onSubmit={(event) => {
        event.preventDefault();
        const query = value.trim();
        if (!query) return;
        // Emitted before navigating, so the query is captured even if the
        // shopper leaves before the results render.
        tracker.track('search', { properties: { query, source: 'header' } });
        router.push(`/search?q=${encodeURIComponent(query)}`);
      }}
    >
      <label htmlFor="store-search" className="sr-only">
        Search products
      </label>
      <Search
        aria-hidden
        className="text-muted-foreground pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
      />
      <input
        id="store-search"
        name="q"
        type="search"
        autoFocus={autoFocus}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Search the catalog…"
        className="border-input bg-surface placeholder:text-muted-foreground h-10 w-full rounded-md border pl-9 pr-3 text-sm"
      />
    </form>
  );
}
