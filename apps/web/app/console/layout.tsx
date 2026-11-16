import Link from 'next/link';
import { ThemeToggle } from '@/components/theme-toggle';

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <header className="border-border border-b">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 rounded-md font-semibold tracking-tight"
          >
            <span className="bg-primary text-primary-foreground grid h-7 w-7 place-items-center rounded-md text-sm font-bold">
              C
            </span>
            CartIQ
          </Link>
          <ThemeToggle />
        </div>
      </header>
      <main id="main" className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        {children}
      </main>
    </div>
  );
}
