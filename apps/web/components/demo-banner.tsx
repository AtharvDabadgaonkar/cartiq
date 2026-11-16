import { TriangleAlert } from 'lucide-react';

/**
 * Required by the honesty rule: a visitor must never be able to mistake this
 * for a real shop, and must know no payment is ever taken.
 */
export function DemoBanner() {
  return (
    <div
      role="note"
      className="border-clay/30 bg-clay/10 text-foreground flex items-center justify-center gap-2 border-b px-4 py-2 text-center text-xs"
    >
      <TriangleAlert aria-hidden className="text-clay h-3.5 w-3.5 shrink-0" />
      <span>
        <strong className="font-semibold">Demo store.</strong> Products and prices come from a
        public dataset. No real payments are processed and no order is ever placed.
      </span>
    </div>
  );
}
