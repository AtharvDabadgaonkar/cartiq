import { ArrowUpRight } from 'lucide-react';
import { buttonVariants } from '@/components/ui/button-variants';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CONSOLE_SECTIONS, consoleUrl } from './sections';

/**
 * The internal console runs as a Streamlit app (apps/console), because the
 * analytics, ML and statistics code is Python and the console is the only
 * consumer of it — one implementation of every metric, no HTTP hop, and a free
 * deploy on Streamlit Community Cloud.
 *
 * This page is the storefront-side entry point and deep-links into it.
 */
export default function ConsolePointerPage() {
  const base = consoleUrl();

  return (
    <div className="space-y-8">
      <section>
        <Badge variant="amber">Python · Streamlit</Badge>
        <h2 className="mt-3 text-2xl font-semibold tracking-tight">
          The conversion intelligence console
        </h2>
        <p className="text-muted-foreground mt-3 max-w-2xl text-sm leading-relaxed">
          Funnel, segments, abandonment, experiments, assistant quality, catalog readiness and the
          insights copilot all run in the Streamlit console, which reads the same Postgres this
          storefront writes to and imports the analytics package directly. The storefront keeps the
          shopper experience: catalog, checkout, AI assistant and event ingestion.
        </p>
        <div className="mt-6">
          <a
            href={base}
            target="_blank"
            rel="noreferrer"
            className={buttonVariants({ size: 'lg' })}
          >
            Open the console <ArrowUpRight aria-hidden className="h-4 w-4" />
          </a>
        </div>
      </section>

      <section>
        <h3 className="text-muted-foreground text-sm font-semibold uppercase tracking-widest">
          Sections
        </h3>
        <ul className="mt-5 grid gap-3 sm:grid-cols-2">
          {Object.entries(CONSOLE_SECTIONS).map(([key, { label, phase, blurb }]) => (
            <li key={key}>
              <Card className="h-full">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>
                      <a
                        href={`${base}/${key}`}
                        target="_blank"
                        rel="noreferrer"
                        className="hover:text-primary hover:underline"
                      >
                        {label}
                      </a>
                    </CardTitle>
                    <Badge variant="neutral">Phase {phase}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription>{blurb}</CardDescription>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
