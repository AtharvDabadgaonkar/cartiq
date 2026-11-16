import { cva, type VariantProps } from 'class-variance-authority';
import type * as React from 'react';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
  {
    variants: {
      variant: {
        neutral: 'border-border bg-surface-raised text-muted-foreground',
        amber: 'border-primary/40 bg-primary/15 text-primary',
        clay: 'border-clay/40 bg-clay/15 text-clay',
        moss: 'border-moss/40 bg-moss/15 text-moss',
        plum: 'border-plum/40 bg-plum/15 text-plum',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
