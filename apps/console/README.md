# CartIQ console (Streamlit)

The internal surface for Product, Growth and Merchandising.

Run locally:

```bash
make dev-console   # http://localhost:8501
```

## How it is wired

- The entrypoint is `streamlit_app.py` at the **repository root**, because
  Streamlit Community Cloud runs a repo-root file. It adds `apps/api/src` and
  `apps/console` to the path and hands off to `cartiq_console.app`.
- The console **imports `cartiq_api` directly** rather than calling the FastAPI
  service over HTTP, so every metric has exactly one implementation.
- Database access is read-only (`cartiq_console/data.py`); the storefront owns
  all writes through Prisma.
- Section list lives in `cartiq_console/sections.py` and is mirrored by
  `apps/web/app/console/sections.ts`, which the storefront uses to deep-link
  here. `apps/api/tests/test_console_parity.py` fails the build if they drift.
- Each section has its own page module in `pages/`; unbuilt ones render the
  shared placeholder from `cartiq_console/placeholder.py`. A phase ships by
  replacing exactly one file.

## Deploying

Streamlit Community Cloud, pointed at this repository:

| Setting | Value |
| --- | --- |
| Main file path | `streamlit_app.py` |
| Python version | 3.11 |
| Dependencies | repo-root `requirements.txt` |
| Secret | `DATABASE_URL` (Supabase pooled connection string) |

Theme comes from `.streamlit/config.toml` and matches the storefront tokens in
`apps/web/app/globals.css`.
