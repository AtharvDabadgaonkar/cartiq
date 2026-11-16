import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

const STEPS = [
  { key: 'shipping', label: 'Shipping' },
  { key: 'payment', label: 'Payment' },
  { key: 'confirm', label: 'Confirmation' },
] as const;

export type CheckoutStepKey = (typeof STEPS)[number]['key'];

export function CheckoutSteps({ current }: { current: CheckoutStepKey }) {
  const currentIndex = STEPS.findIndex((step) => step.key === current);

  return (
    <nav aria-label="Checkout progress">
      <ol className="flex items-center gap-2 text-sm">
        {STEPS.map((step, index) => {
          const done = index < currentIndex;
          const active = index === currentIndex;
          return (
            <li key={step.key} className="flex items-center gap-2">
              <span
                className={cn(
                  'grid h-6 w-6 place-items-center rounded-full text-xs font-semibold',
                  done && 'bg-moss text-moss-foreground',
                  active && 'bg-primary text-primary-foreground',
                  !done && !active && 'border-border text-muted-foreground border',
                )}
                aria-hidden
              >
                {done ? <Check className="h-3 w-3" /> : index + 1}
              </span>
              <span
                className={cn(active ? 'font-medium' : 'text-muted-foreground')}
                aria-current={active ? 'step' : undefined}
              >
                {step.label}
              </span>
              {index < STEPS.length - 1 && (
                <span aria-hidden className="bg-border mx-1 h-px w-6 sm:w-10" />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
