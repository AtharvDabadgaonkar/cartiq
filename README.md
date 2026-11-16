# CartIQ

**AI Commerce Experience & Conversion Intelligence Platform**

Commerce teams know their conversion rate. Few can say which specific moment of
the journey is costing them the quarter, what to ship against it, or whether
what they shipped actually worked.

CartIQ maps the shopper journey against a real public e-commerce behaviour
dataset, ships AI-powered interventions where the drop-off actually is, and
proves their impact through a built-in A/B experiment studio.

**Diagnose → Intervene → Measure → Scale**

> ### 🚧 Build status: Phase 1 of 9 complete (foundation)
>
> This README quotes **no metrics yet**, by design. Every figure in this project
> must be produced by `make metrics` into [`reports/metrics.json`](reports/metrics.json);
> none are hand-written. Screenshots, the live demo link and the key-metrics
> table land in Phase 9.

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
make db-up     # Postgres with pgvector, on port 5433
make migrate   # Prisma migrations + SQL models
make dev       # storefront :3000 · console :8501 · api :8000
```

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

## Build phases

| # | Phase | Status |
| --- | --- | --- |
| 1 | Foundation — monorepo, schema, tracking SDK, console shell, CI, mock LLM | ✅ |
| 2 | Data — ingestion, seed sample, catalog, session simulator | — |
| 3 | Storefront — pages, checkout, event tracking, Playwright | — |
| 4 | Diagnose — SQL models, funnel, KPIs, segmentation, friction | — |
| 5 | Abandonment — risk model, metrics report, nudge engine | — |
| 6 | AI assistant — pgvector retrieval, chat, recommendations, eval | — |
| 7 | Experiment Studio — assignment, stats, guardrails, AI readout | — |
| 8 | Scale — insights copilot with SQL safety, catalog readiness | — |
| 9 | Polish & ship — overview story, PRD, README metrics, deploy to Vercel + Streamlit + Supabase | — |

## Licence and data

Code: MIT. The source datasets (REES46 / Olist) are licensed by their
publishers and are **not** committed; `scripts/ingest.py` documents the download
steps. A small seed sample is committed so the app runs out of the box.
