# CartIQ

**AI Commerce Experience & Conversion Intelligence Platform**

# Live storefront: https://cartiq-sigma.vercel.app/

# ▶️ Live demo: https://cartiq-crvu6q7r2qcdxmckzm7uae.streamlit.app/


Commerce teams know their conversion rate. Few can say which specific moment of
the journey is costing them the quarter, what to ship against it, or whether
what they shipped actually worked.

CartIQ maps the shopper journey against a real public e-commerce behaviour
dataset, ships AI-powered interventions where the drop-off actually is, and
proves their impact through a built-in A/B experiment studio.

**Diagnose → Intervene → Measure → Scale**

> ### 🚧 Build status: Phase 5 of 9 complete (abandonment)
>
> Every figure below is produced by `make metrics` into
> [`reports/metrics.json`](reports/metrics.json) and carries its own provenance.
> None are hand-written. Screenshots and the live demo link land in Phase 9.

## What the diagnosis found

| Finding | Figure | Source |
| --- | --- | --- |
| Biggest leak | Product View -> Add to Cart — 78.9% of sessions lost there | simulated |
| Share of all modelled revenue loss at that one step | 54% | simulated |
| Cart abandonment | 80.6% | simulated |
| Searchers convert better than average | 2.72% vs 1.80% overall | simulated |
| Revenue concentration | **Champions** are 14% of customers but 53% of revenue | **real** |

The last row is the one worth pausing on: it comes from real purchase
behaviour, and it says a pricing or delivery change that annoys one customer in
seven puts half the revenue at risk.

**Why the funnel is simulated and the segments are real.** The real dataset
records purchases, not browsing — it has no device, no traffic source and no
session beyond the invoice, so every session in it converted by construction.
CartIQ therefore *refuses* to compute conversion rate, revenue per visitor or
cart abandonment from it, and says why in the UI instead of rendering a 100%
conversion rate that would look entirely plausible. Journey metrics come from
simulated sessions and are labelled; value and segmentation metrics come from
the real rows.

## The abandonment model, reported honestly

| | |
| --- | --- |
| Trained on | 47,458 carting sessions (simulated) |
| Selected model | **logistic regression** |
| ROC AUC | 0.611 |
| Average precision | 0.853 vs 0.802 majority-class baseline |
| Brier score | 0.1551 |

Three things worth saying plainly:

- **The gradient-boosted model did not beat the logistic baseline.** That is
  reported, not buried. The simulator generates abandonment from additive
  device, segment and channel effects, so there is little non-linear structure
  to find — shipping the simpler model is the right call.
- **AUC 0.61 is a weak ranker**, and it is quoted as such. What matters more
  for this use is that the model is *calibrated*: the nudge engine fires on a
  probability threshold, so a predicted 80% has to mean 80%. The worst
  calibration gap on any well-populated bin is under 5 percentage points, and a
  test enforces it.
- **No post-cart feature is used.** `mart_cart_sessions` excludes every funnel
  step after the cart is created, because a model that knows the shopper
  reached the payment step would score beautifully and be undeployable.

The nudge engine is **rules, not a model**: the model gives a calibrated score,
the rules decide what to say. At most one message per cart — stacking them
turns a helpful nudge into a dark pattern, and would make the experiment
uninterpretable. Each nudge sits behind its own feature flag.

## The storefront

A working demo shop over the real catalog: home, search, category and product
pages, a persistent cart, and a three-step checkout (shipping → payment →
confirmation). Every funnel step emits its event from the component that
performs it, so the funnel measures intent rather than navigation.

Two deliberate choices a reader should notice:

- **There is no card-number field anywhere in this app.** A demo that renders
  one invites a visitor to type a real card into a toy. The payment step shows a
  fixed, obviously fake method and the button only records the `purchase` event.
- **Nothing the source data lacks is invented.** Products show "not in source
  data" for brand and GTIN, derived values are badged `derived`, and the image
  placeholder says there is no image rather than substituting a stock photo.

## The data, as loaded

| | Real dataset | Simulated |
| --- | --- | --- |
| Events | 84,473 | 32,793 |
| Orders / sessions | 3,000 invoices | 12,000 sessions |
| Customers | 1,412 | — |
| Catalog products | 3,331 | uses the real catalog |
| Return lines | 1,811 | — |

Those are the committed seed sample (`make seed`), which is what a clean
checkout gets. `make ingest` loads the full dataset instead — about twelve times
the rows — and prints its own reconciliation of every source row to a loaded
event, a return line, or a named drop reason. Re-run `make metrics` afterwards
and the table above reports the full figures.

**What the real data can and cannot measure.** Online Retail II records
*purchases*, not browsing. It has no device, no traffic source, no page and no
session beyond the invoice, and 28.5% of its lines have no customer
id at all. So CartIQ applies one rule everywhere: **a field a source cannot
observe is `NULL` or `unknown`, never invented.** The journey funnel above
`purchase` is therefore measured on *simulated* sessions and labelled as such;
value metrics, segmentation and the catalog come from the real rows.

The catalog makes the same point. Title and price are real;
74% of products get a category derived from their real description
(the rest stay `uncategorised` rather than being forced into a bucket); and
brand, GTIN and image coverage are **0%** — not a bug, but the genuine
state of the catalog, and exactly what the Phase 8 AI-readiness score exists to
measure.

## On data honesty

| What | Source | How it is labelled |
| --- | --- | --- |
| Journey, funnel, segments, friction, abandonment model | A **real** public e-commerce behaviour dataset | `Real dataset` |
| Experiment results and lifts | **Simulated** sessions from `scripts/simulate.py` with documented parameters | `Simulated` — everywhere, always |
| Your clicks in the demo storefront | Live demo traffic | `Demo traffic` |

Provenance is a column (`events.source`), not a convention, and every console
surface reports which sources its numbers cover. The simulator's behavioural
assumptions — including the treatment effect of each intervention — are explicit
configurable parameters documented in [`docs/SIMULATION.md`](docs/SIMULATION.md).
The Experiment Studio is never told what the effect is: it has to recover it
through correct statistics, and the test suite asserts that it does.

## What is in here

| Module | Stage | Phase |
| --- | --- | --- |
| Journey & funnel analytics | Diagnose | 4 |
| Customer segmentation (RFM + k-means) | Diagnose | 4 |
| Cart abandonment & UX friction, risk model, nudge engine | Diagnose → Intervene | 5 |
| AI shopping assistant + personalisation | Intervene | 6 |
| A/B Experiment Studio | Measure | 7 |
| AI insights copilot + catalog readiness | Scale | 8 |

## Quick start

Requires Docker, Node 20+, pnpm and Python 3.11.

```bash
make install   # JS + Python dependencies, creates .env from .env.example
make data      # Postgres + migrations + the committed seed sample
make dev       # storefront :3000 · console :8501 · api :8000
```

Then, optionally:

```bash
make ingest      # the full real dataset (44MB, downloads without credentials)
make simulate    # 500k simulated sessions (see docs/SIMULATION.md)
make metrics     # recompute every number quoted here
make snapshot    # export the console's analytics for a database-free deploy
```

The hosted console runs with **no database**. `make snapshot` runs the real SQL
models and commits their *results* to `data/snapshot/` (~0.4 MB), and the
console reads those when no `DATABASE_URL` is set, saying on every page that it
is a snapshot and when it was taken. Nothing is reimplemented against files, so
the hosted figures cannot disagree with the warehouse — a test re-checks the
committed files against a live query. Filters other than the data source are
hidden in that mode, because a snapshot holds one slice per source. Details in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

No API key is needed: `LLM_PROVIDER=mock` is the default and the mock provider
is deterministic and grounding-faithful, so the whole app and the full test
suite run offline.

```bash
make test      # Vitest (web + packages) and pytest
make lint      # ESLint + Ruff
make typecheck # tsc + mypy
make metrics   # recompute every quoted number -> reports/metrics.json
make help      # all targets
```

## Architecture

Monorepo on pnpm workspaces:

| Path | What |
| --- | --- |
| `apps/web` | Next.js 15 storefront, AI assistant, event ingest, Prisma schema |
| `apps/console` | Streamlit internal console: funnel, segments, experiments, copilot |
| `apps/api` | `cartiq_api`: analytics, ML, experiment statistics, session simulator |
| `packages/shared` | Event schema (Zod), funnel definition, deterministic assignment |
| `packages/tracking` | Browser tracking SDK: batching, retry, client-side validation |
| `models/` | Versioned SQL views (staging → intermediate → marts) |
| `scripts/` | ingest, seed, simulate, metrics, SQL model runner |
| `reports/` | `metrics.json` — the only source for any number quoted anywhere |

Stack: TypeScript, Next.js 15, Tailwind, Prisma, Postgres + pgvector,
Python 3.11, Streamlit, FastAPI, pandas, scikit-learn, scipy, statsmodels.

### Two front ends, one database

The product has two audiences with nothing in common, so it has two surfaces:

| Surface | Who | Stack | Host (free tier) |
| --- | --- | --- | --- |
| **Storefront** `/` | Shoppers | Next.js 15 | Vercel |
| **Console** | Product, Growth, Merchandising | Streamlit | Streamlit Community Cloud |
| **Database** | both | Postgres + pgvector | Supabase |

The console **imports the Python analytics package directly** instead of calling
it over HTTP, so every metric has exactly one implementation — used by the
console, the scripts and the test suite alike — and there is no third service to
cold-start. The storefront's `/console` route deep-links into it, and a parity
test fails the build if the two declarations of the section list drift.

The decisions behind that — Prisma over Drizzle, plain SQL views over dbt, the
two-front-end split, and hash-based assignment with no assignment table — are
written up with their trade-offs in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Documentation

| Doc | What it covers |
| --- | --- |
| [PRD](docs/PRD.md) | Problem, users, goals, scope, KPI tree, risks, roadmap |
| [Architecture](docs/ARCHITECTURE.md) | System shape and every key decision with its trade-off |
| [Simulation](docs/SIMULATION.md) | Every simulator assumption and parameter, in plain language |
| [Experiment readout](docs/EXPERIMENT_READOUT.md) | Generated from a real run in Phase 7 |
| [Launch plan](docs/LAUNCH_PLAN.md) | Flag rollout stages, go/no-go criteria, rollback triggers |
| [Metrics dictionary](docs/METRICS_DICTIONARY.md) | Every metric: definition, formula, grain, provenance |
| [Deployment](docs/DEPLOYMENT.md) | Supabase + Streamlit Cloud + Vercel, in order, with the free-tier limits |

## Build phases

| # | Phase | Status |
| --- | --- | --- |
| 1 | Foundation — monorepo, schema, tracking SDK, console shell, CI, mock LLM | ✅ |
| 2 | Data — ingestion, seed sample, catalog, session simulator | ✅ |
| 3 | Storefront — pages, checkout, event tracking, Playwright | ✅ |
| 4 | Diagnose — SQL models, funnel, KPIs, segmentation, friction | ✅ |
| 5 | Abandonment — risk model, metrics report, nudge engine | ✅ |
| 6 | AI assistant — pgvector retrieval, chat, recommendations, eval | — |
| 7 | Experiment Studio — assignment, stats, guardrails, AI readout | — |
| 8 | Scale — insights copilot with SQL safety, catalog readiness | — |
| 9 | Polish & ship — overview story, PRD, README metrics, deploy to Vercel + Streamlit + Supabase | — |

## Licence and data

Code: MIT.

The real dataset is **Online Retail II** from the UCI Machine Learning
Repository, used under **CC BY 4.0**:

> Chen, D. (2019). *Online Retail II* [Dataset]. UCI Machine Learning
> Repository. <https://doi.org/10.24432/C5CG6D>. Licensed CC BY 4.0.

It downloads without credentials, so `make ingest` works on a clean checkout.
The committed seed in `data/seed/` is a genuine extract of it (the earliest
3,000 invoices), redistributed under the same licence with attribution
recorded in `data/seed/manifest.json` and in the `dataset_imports` table.
