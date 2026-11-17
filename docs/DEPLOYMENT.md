# Deploying CartIQ

Three free-tier services, in this order. The order matters: the console and the
storefront both need the database to exist first.

| Piece | Host | Needs |
| --- | --- | --- |
| Postgres + pgvector | Supabase | a Supabase account |
| Console | Streamlit Community Cloud | a public GitHub repo (done) |
| Storefront | Vercel | a Vercel account |

---

## 1. Database (Supabase)

1. Create a project at <https://supabase.com/dashboard>. Pick a region near you
   and save the database password — it is shown once.
2. In **Project Settings → Database → Connection string**, copy both:
   - the **pooled** (Transaction) URI — this is `DATABASE_URL`
   - the **direct** URI — this is `DIRECT_URL`, used only for migrations

Prisma needs both: migrations cannot run through a transaction pooler.

3. From your machine, point at it and build the schema:

```bash
export DATABASE_URL="<pooled URI>"
export DIRECT_URL="<direct URI>"
pnpm --filter @cartiq/web exec prisma migrate deploy
apps/api/.venv/bin/python scripts/build_models.py
apps/api/.venv/bin/python scripts/seed.py
```

### Watch the size limit

Supabase's free tier caps the database at **500 MB**. The committed seed is
120,706 events (84,473 real + 36,233 simulated, per `data/seed/manifest.json`)
and fits comfortably. A full `make simulate` run is ~1.5M events and will
**not** fit.

The seed's 12,000 simulated sessions are enough for the overview, funnel and
segment pages, but they yield only ~1.1k carting sessions -- below the 2,000
the abandonment model requires -- so that page will honestly report too little
data. To light it up, add a larger run:

```bash
apps/api/.venv/bin/python scripts/simulate.py --sessions 120000
```

That gives ~13k carting sessions, enough to train and calibrate the
abandonment model, and lands around 300 MB with the seed. It is *not* enough
to power the Phase 7 experiment, which needs ~500k sessions — run that one
locally and publish the readout rather than the raw events.

---

## 2. Console (Streamlit Community Cloud)

1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. **New app** → pick the repo, branch `main`.

| Setting | Value |
| --- | --- |
| Main file path | `streamlit_app.py` |
| Python version | 3.11 |

3. Under **Advanced settings → Secrets**, paste:

```toml
DATABASE_URL = "<pooled Supabase URI>"
LLM_PROVIDER = "mock"
FLAG_HASH_SALT = "cartiq-v1"
```

`FLAG_HASH_SALT` must match whatever generated your data, or experiment
assignments computed in the console will not agree with the stored ones.

Dependencies come from the repo-root `requirements.txt`, which installs
`./apps/api` so the console can import the analytics package directly.

### If it fails to start

- **`ModuleNotFoundError: cartiq_api`** — `requirements.txt` was not picked up.
  It must be at the repo root, not in `apps/console/`.
- **Blank page, no database** — the console detects this and says so rather
  than crashing. Check the secret name is exactly `DATABASE_URL`.
- **Slow first load** — the free tier sleeps when idle; the first request after
  a quiet period wakes the container.

---

## 3. Storefront (Vercel)

1. <https://vercel.com/new> → import the repo.

| Setting | Value |
| --- | --- |
| Root directory | `apps/web` |
| Framework | Next.js (detected) |
| Build command | `pnpm --filter @cartiq/web build` |

2. Environment variables:

```
DATABASE_URL          = <pooled Supabase URI>
DIRECT_URL            = <direct Supabase URI>
LLM_PROVIDER          = mock
FLAG_HASH_SALT        = cartiq-v1
NEXT_PUBLIC_CONSOLE_URL = https://<your-app>.streamlit.app
```

`NEXT_PUBLIC_CONSOLE_URL` is what makes the storefront's `/console` route
deep-link into the deployed console instead of `localhost:8501`.

Storefront routes are `force-dynamic`, so the build does not need the database —
but the running app does.

---

## After deploying

Put the live links at the top of `README.md`. A reader should be able to open
the shop, place a mock order, and then see their own session counted in the
console — that round trip is the whole argument of the project, and it is worth
being one click away.

## What is NOT deployed

- **The FastAPI service.** The console imports the analytics package directly,
  so there is no second service to host. `apps/api` still runs locally for
  development and is still fully tested.
- **The raw dataset.** 44 MB, gitignored, downloaded on demand by
  `make ingest`. The committed 1.2 MB seed is what a clean deploy uses.
