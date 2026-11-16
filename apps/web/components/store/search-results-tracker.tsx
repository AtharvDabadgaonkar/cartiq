'use client';

import { useEffect, useRef } from 'react';
import { useTracker } from '@/components/providers/tracking-provider';

/**
 * Emits `search` with its result count once per distinct query.
 *
 * The header search box already emits on submit; this covers arriving at a
 * results URL directly (a shared link, a back-navigation, a category refine),
 * and is what lets search-to-purchase be measured from the results actually
 * shown rather than only from typed queries.
 */
export function SearchResultsTracker({
  query,
  resultCount,
}: {
  query: string;
  resultCount: number;
}) {
  const tracker = useTracker();
  const lastQuery = useRef<string | null>(null);

  useEffect(() => {
    if (!query) return;
    const key = `${query}:${resultCount}`;
    if (lastQuery.current === key) return;
    lastQuery.current = key;
    tracker.track('search', {
      properties: { query, result_count: resultCount, source: 'results_page' },
    });
  }, [tracker, query, resultCount]);

  return null;
}
