import type { Metadata } from 'next';
import { themeScript } from '@/components/theme-toggle';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'CartIQ — Commerce Experience & Conversion Intelligence',
    template: '%s · CartIQ',
  },
  description:
    'Diagnose where shoppers drop off, ship AI-powered interventions, and prove their impact with a built-in experiment studio.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        {/* Avoids a theme flash; see components/theme-toggle.tsx. */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh font-sans">
        <a
          href="#main"
          className="focus:bg-primary focus:text-primary-foreground sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
