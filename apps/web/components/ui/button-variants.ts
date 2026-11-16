import { cva, type VariantProps } from 'class-variance-authority';

/**
 * Kept in its own module (no 'use client') so server components can use the
 * class string on a `<Link>` without pulling in the client Button component.
 */
export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
        clay: 'bg-clay text-clay-foreground hover:bg-clay/90',
        outline: 'border border-border bg-transparent hover:bg-surface-raised',
        ghost: 'hover:bg-surface-raised',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-8 px-3',
        md: 'h-10 px-4',
        lg: 'h-11 px-6 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export type ButtonVariantProps = VariantProps<typeof buttonVariants>;
