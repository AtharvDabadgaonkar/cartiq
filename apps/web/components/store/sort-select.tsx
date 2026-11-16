'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import type { SortKey } from '@/lib/catalog-shared';

const OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'popular', label: 'Best selling' },
  { value: 'price_asc', label: 'Price: low to high' },
  { value: 'price_desc', label: 'Price: high to low' },
  { value: 'title', label: 'Name A–Z' },
];

export function SortSelect({ value }: { value: SortKey }) {
  const router = useRouter();
  const params = useSearchParams();

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="sort" className="text-muted-foreground text-sm">
        Sort
      </label>
      <select
        id="sort"
        value={value}
        onChange={(event) => {
          const next = new URLSearchParams(params?.toString());
          next.set('sort', event.target.value);
          next.delete('page');
          router.push(`?${next.toString()}`);
        }}
        className="border-input bg-surface h-9 rounded-md border px-2 text-sm"
      >
        {OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
