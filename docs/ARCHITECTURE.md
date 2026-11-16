# CartIQ — Architecture

> Status: written in Phase 1. Updated at the end of each phase.

## 1. Shape of the system

```
                 ┌──────────────────────────────────────┐
  shopper ──────▶│  apps/web  (Next.js 15, App Router)  │   deployed to Vercel
                 │    /        storefront + assistant   │
                 │    /api/*   event ingest, flags      │
                 └──────────────┬───────────────────────┘
                                │ Prisma (the only writer)
                                ▼
                       ┌────────────────────┐
                       │  Postgres          │  Supabase
                       │  + pgvector        │
                       │   events           │
                       │   products         │
                       │   experiments      │
                       │   llm_calls        │
                       └───┬────────────┬───┘
      CREATE OR REPLACE ───┘            │ read-only (SQLAlchemy)
                ▼                       ▼
     models/*.sql              ┌──────────────────────────────────┐
     staging → marts           │  apps/console  (Streamlit)       │ deployed to
                               │    funnel / segments / RFM       │ Streamlit
  PM / growth ────────────────▶│    abandonment model             │ Community
                               │    experiment statistics         │ Cloud
                               │    copilot / catalog readiness   │
                               └───────────────┬──────────────────┘
                                               │ imports, no HTTP hop
                                               ▼
                                   apps/api  (cartiq_api package)
                                   analytics · ML · statistics · simulator
                                   also served by FastAPI for local dev
```

Shared contracts live in `packages/`:

- `packages/shared` — the event schema (Zod), the funnel definition, and the
  deterministic assignment function. Mirrored in Python under
  `apps/api/src/cartiq_api/{schemas,assignment}.py`, with a parity test that
  fails the build on drift.
- `packages/tracking` — the browser tracking SDK: context resolution, batching,
  retry, client-side validation.

## 2. Key decisions

### 2.1 Prisma for schema and migrations

Prisma owns the schema and every write. Reasons: generated types flow straight
into the Next.js app, `migrate dev`/`migrate deploy` is the least ceremonious
migration story on Vercel + Supabase, and the schema file doubles as readable
documentation of the data model.

Trade-off: Prisma has no `vector` type. The embedding column is declared
`Unsupported("vector(384)")` and all ANN queries go through `$queryRaw` with the
`<=>` operator. That is a small, contained amount of raw SQL in one module.

The Python service reads through SQLAlchemy Core and never writes application
tables, so there is exactly one writer and no migration race.

### 2.2 Versioned SQL views, not dbt

Chosen: plain `CREATE OR REPLACE VIEW` files in `models/`, applied in filename
order by `scripts/build_models.py`.

Why not dbt: the warehouse is a single Postgres database with roughly fifteen
models, no incremental materialisation, no multi-target deployment, and no
cross-project lineage. dbt-core + dbt-postgres would add a second dependency
tree, a profiles file, a second test framework and a second place to look for a
metric definition. The runner it replaces is about sixty lines.

What is given up: lineage graphs, `dbt docs`, and dbt's own tests. The first two
are not needed at this size; metric correctness is instead asserted by Python
tests that reconcile every console figure against direct SQL
(`apps/api/tests/test_funnel_reconciliation.py`, Phase 4).

Escape hatch: because every model is a plain `.sql` file with a staging →
intermediate → mart naming convention, adopting dbt later is a mechanical move.

### 2.3 Two front ends: Next.js for shoppers, Streamlit for the team

The product has two audiences with nothing in common. Shoppers need a fast,
accessible, SEO-shaped storefront with an embedded AI assistant — that is
Next.js on Vercel. Product, Growth and Merchandising need charts over the output
of pandas, scikit-learn, scipy and statsmodels — that is Streamlit.

`apps/console` (Streamlit) **imports `cartiq_api` directly** rather than calling
it over HTTP. Consequences, all of them deliberate:

- Every metric has exactly one implementation, in Python, used by the console,
  the scripts and the tests alike. No TypeScript reimplementation to drift.
- No third hosting service. The analytics code deploys as part of the console,
  so there is no Render instance to cold-start and nothing to keep awake.
- `apps/api`'s FastAPI app still exists and is still tested, because the
  storefront needs a couple of endpoints in local development and because
  keeping the HTTP boundary intact means the service can be split out later
  without moving code.

What is given up: Streamlit reruns the whole script on interaction, so heavy
queries must be cached (`@st.cache_data`) rather than streamed. At this data
size that is a non-issue, and the cache TTLs are set in `apps/console/cartiq_console/data.py`.

The storefront's `/console` route is a pointer page that deep-links into the
Streamlit app by section key. The IA is declared in both languages and a parity
test (`apps/api/tests/test_console_parity.py`) fails the build if they drift.

### 2.4 Deterministic assignment, no assignment table

Assignment is a pure function: `FNV-1a(salt:experiment:unit) % 10000`, walked
against cumulative variant weights. No storage, no race, identical in the
browser and in the simulator. The two implementations are pinned to shared test
vectors (`packages/shared/src/__fixtures__/assignment-vectors.json`) asserted by
both test suites.

Exposure (staged rollout) uses a *separate* hash namespace, so ramping 1% → 10%
→ 50% never reassigns a unit that was already exposed — the single most common
way a staged rollout invalidates its own experiment.

`experiment_exposures` exists only for the sample-ratio-mismatch check and
debugging; it is never read to decide a variant.

### 2.5 LLM behind one interface, mock by default

`apps/web/lib/llm` exposes `complete()` and `embed()`; providers are `mock`,
`anthropic` and `openai`, selected by `LLM_PROVIDER`. The default is `mock`, so
the app and the entire test suite run with no API key.

The mock is deliberately not a fixed-string stub. It is deterministic and
grounding-faithful: it ranks the supplied context against the question, cites
only ids it was given, and emits the refusal sentinel when the context cannot
support an answer. That keeps the Module 4 grounding and hallucination tests
meaningful in CI.

Every call is logged to `llm_calls` with the exact grounding chunks it was
given, which is what makes the assistant-quality guardrail computable after the
fact rather than only live.

### 2.6 A field a source cannot observe is NULL, never invented

The real dataset records purchases, not browsing: no device, no traffic source,
no page, no session beyond the invoice, and 22.8% of lines carry no customer id.
Loading it into an event schema that requires those fields would mean
fabricating them.

So the schema was relaxed instead, under one rule applied everywhere:

| Field | How an unobservable value is recorded |
| --- | --- |
| `device`, `traffic_source` | `unknown` enum member |
| `page`, `is_new_user` | `NULL` |
| `user_id` | `NULL` (anonymous line, kept so revenue still reconciles) |
| `brand`, `gtin`, `image_url`, `description` | `NULL` on the product |

Each dataset also declares `observable_steps` — the funnel steps it can actually
measure — and the console reads that rather than assuming every step is
measurable. For a transactional source it is `("visit", "purchase")`, so the
journey funnel is shown from simulated sessions and labelled.

The alternative, filling in a plausible device split, would have produced a
mobile-vs-desktop funnel that looked entirely convincing and meant nothing.

### 2.7 Derived catalog fields are flagged, absent ones stay absent

Category and attributes are derived from the real product description by
deterministic rules and recorded in `generated_fields` so the UI can mark them.
Brand, GTIN and images are simply absent from the source, so they stay `NULL`:
guessing a brand is a fabrication a merchandiser could act on. That the real
coverage of those fields is 0% is a genuine finding, and the input to the
Phase 8 AI-readiness score.

### 2.8 Provenance is a column, not a convention

`events.source` is `REAL_DATASET | SIMULATED | LIVE_DEMO`. `dataset_imports`
records the licence, attribution, file checksum, every drop reason and the
observable steps for each real import; `simulation_runs` stores the seed, the
full parameter set and the ground truth for each simulated batch. Ingestion is
idempotent: event ids are UUIDv5 over the source's natural key, so a re-run
inserts nothing. Every API response and every console surface reports which sources it
covers. This is what makes the honesty rule enforceable rather than aspirational.

## 3. Repository layout

| Path | Contents |
| --- | --- |
| `apps/web` | Next.js storefront, event ingest, Prisma schema |
| `apps/api` | `cartiq_api`: analytics, ML, statistics, simulator (+ a FastAPI app for local dev) |
| `apps/console` | Streamlit internal console — the team-facing surface |
| `packages/shared` | Event schema, funnel definition, assignment function |
| `packages/tracking` | Browser tracking SDK |
| `packages/eslint-config` | Shared flat ESLint config |
| `models/` | Versioned SQL views |
| `scripts/` | ingest, seed, build_seed, simulate, metrics, model runner |
| `docs/` | PRD, this file, simulation, readout, launch plan, metrics dictionary |
| `reports/` | `metrics.json` — the only source for any number quoted anywhere |

## 4. Local and deployed topology

Local: `make dev` starts Dockerised Postgres (pgvector, port 5433), the Next.js
dev server on 3000, the Streamlit console on 8501 and uvicorn on 8000.

Deployed, all free tier:

| Piece | Host | Notes |
| --- | --- | --- |
| Storefront + event ingest | Vercel | `apps/web`, Prisma migrations on deploy |
| Internal console | Streamlit Community Cloud | repo-root `streamlit_app.py` + `requirements.txt`; needs a public GitHub repo |
| Postgres + pgvector | Supabase | pooled URL for the app, direct URL for migrations |

`NEXT_PUBLIC_CONSOLE_URL` points the storefront at the deployed console;
`DATABASE_URL` is set as a Streamlit secret.

## 5. Testing strategy

| Layer | Tool | What it guards |
| --- | --- | --- |
| Event schema | Vitest + pytest | Validation parity between Zod, Pydantic and Prisma enums |
| Assignment | Vitest + pytest | Cross-language hash equality, split balance, exposure ramping |
| Tracking SDK | Vitest | Batching, retry, invalid-event rejection, unload behaviour |
| LLM seam | Vitest | Grounding, refusal, citation extraction, call logging |
| Metrics | pytest | Console figures reconciled against direct SQL (Phase 4) |
| Stats engine | pytest | Recovers a known simulated effect; A/A false-positive rate; SRM detection (Phase 7) |
| Console IA | pytest | Storefront deep-links match the console's own section list |
| Dataset cleaning | pytest | Every source row reconciles to a load, a return or a named drop |
| Catalog | pytest | Derived fields flagged; absent fields stay NULL |
| Simulator | pytest | Determinism; an effect lands only on its own transition; A/A is exactly zero |
| Simulator docs | pytest | Every parameter in code is documented in SIMULATION.md |
| Journeys | Playwright | Storefront flows and event emission (Phase 3) |
