import { ArrowRight, BarChart3, FlaskConical, Sparkles, Stethoscope } from 'lucide-react';
import Link from 'next/link';
import { DemoBanner } from '@/components/demo-banner';
import { ThemeToggle } from '@/components/theme-toggle';
import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button-variants';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const NARRATIVE = [
  {
    icon: Stethoscope,
    step: 'Diagnose',
    title: 'Find where the money leaks',
    body: 'Journey funnel, RFM + behavioural segments, and a revenue-weighted ranking of every friction point — computed from a real public e-commerce behaviour dataset.',
    tone: 'clay' as const,
  },
  {
    icon: Sparkles,
    step: 'Intervene',
    title: 'Ship something against it',
    body: 'A catalog-grounded shopping assistant, co-occurrence personalisation, and risk-triggered cart-recovery nudges — each independently gated by a feature flag.',
    tone: 'amber' as const,
  },
  {
    icon: FlaskConical,
    step: 'Measure',
    title: 'Prove it moved',
    body: 'Experiment Studio with deterministic assignment, two-proportion z / Welch tests, confidence intervals, sample-ratio-mismatch checks and guardrail metrics.',
    tone: 'moss' as const,
  },
  {
    icon: BarChart3,
    step: 'Scale',
    title: 'Make it repeatable',
    body: 'An insights copilot over allow-listed read-only views, and a catalog-readiness score for how findable each product is to an AI shopping agent.',
    tone: 'plum' as const,
  },
];

const PHASES = [
  { n: 1, name: 'Foundation', done: true },
  { n: 2, name: 'Data & simulator', done: true },
  { n: 3, name: 'Storefront', done: true },
  { n: 4, name: 'Diagnose', done: true },
  { n: 5, name: 'Abandonment', done: true },
  { n: 6, name: 'AI assistant', done: false },
  { n: 7, name: 'Experiment Studio', done: false },
  { n: 8, name: 'Scale', done: false },
  { n: 9, name: 'Polish & ship', done: false },
];

export const metadata = { title: 'About this project' };

export default function AboutPage() {
  return (
    <>
      <DemoBanner />
      <header className="border-border border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <Link
            href="/"
            className="flex items-center gap-2 rounded-md font-semibold tracking-tight"
          >
            <span className="bg-primary text-primary-foreground grid h-7 w-7 place-items-center rounded-md text-sm font-bold">
              C
            </span>
            CartIQ
          </Link>
          <nav className="flex items-center gap-1">
            <Link href="/" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
              Shop
            </Link>
            <Link href="/console" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
              Console
            </Link>
            <ThemeToggle />
          </nav>
        </div>
      </header>

      <main id="main" className="ember-glow">
        <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
          <Badge variant="amber">Portfolio build · Phase 5 of 9 complete</Badge>
          <h1 className="mt-5 max-w-3xl text-balance text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
            Most commerce teams know their conversion rate.
            <span className="text-primary">
              {' '}
              Few can tell you which 40 seconds of the journey is costing them the quarter.
            </span>
          </h1>
          <p className="text-muted-foreground mt-5 max-w-2xl text-lg">
            CartIQ maps the shopper journey against a real behaviour dataset, ships AI-powered
            interventions where the drop-off actually is, and proves their impact through a built-in
            A/B experiment studio.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/" className={buttonVariants({ size: 'lg' })}>
              Browse the demo store <ArrowRight aria-hidden className="h-4 w-4" />
            </Link>
            <Link href="/console" className={buttonVariants({ size: 'lg', variant: 'outline' })}>
              Open the console
            </Link>
          </div>
          <p className="text-muted-foreground mt-6 max-w-2xl text-sm">
            <strong className="text-foreground">On data honesty:</strong> diagnosis runs on a real
            public dataset. Experiment results run on simulated sessions with documented parameters
            and are labelled <em>simulated</em> everywhere they appear — in the UI, the README and
            the readout.
          </p>
        </section>

        <section className="border-border bg-surface/40 border-t">
          <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
            <h2 className="text-muted-foreground text-sm font-semibold uppercase tracking-widest">
              The loop
            </h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {NARRATIVE.map(({ icon: Icon, step, title, body, tone }) => (
                <Card key={step} className="animate-fade-up">
                  <CardHeader>
                    <Badge variant={tone} className="w-fit">
                      <Icon aria-hidden className="h-3 w-3" />
                      {step}
                    </Badge>
                    <CardTitle className="mt-2">{title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription>{body}</CardDescription>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
          <h2 className="text-muted-foreground text-sm font-semibold uppercase tracking-widest">
            Build progress
          </h2>
          <ol className="mt-6 grid gap-2 sm:grid-cols-3">
            {PHASES.map((phase) => (
              <li
                key={phase.n}
                className="border-border bg-surface flex items-center gap-3 rounded-md border px-4 py-3 text-sm"
              >
                <span
                  aria-hidden
                  className={
                    phase.done
                      ? 'bg-moss text-moss-foreground grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-bold'
                      : 'border-border text-muted-foreground grid h-6 w-6 shrink-0 place-items-center rounded-full border text-xs'
                  }
                >
                  {phase.n}
                </span>
                <span className={phase.done ? 'font-medium' : 'text-muted-foreground'}>
                  {phase.name}
                </span>
                <span className="sr-only">{phase.done ? 'complete' : 'not started'}</span>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="border-border border-t">
        <div className="text-muted-foreground mx-auto max-w-6xl px-4 py-8 text-sm sm:px-6">
          CartIQ — a portfolio build. Every figure quoted in this project is reproduced by{' '}
          <code className="bg-surface-raised rounded px-1.5 py-0.5 font-mono text-xs">
            make metrics
          </code>{' '}
          and written to{' '}
          <code className="bg-surface-raised rounded px-1.5 py-0.5 font-mono text-xs">
            reports/metrics.json
          </code>
          .
        </div>
      </footer>
    </>
  );
}
