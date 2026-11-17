# SQL models

Versioned SQL views, applied in filename order by `scripts/build_models.py`
(`make migrate` runs it after Prisma migrations).

**Why plain SQL views instead of dbt** — the whole warehouse is one Postgres
database with roughly fifteen models and no cross-warehouse lineage. dbt would
add a second dependency tree, a profiles file, and a second test framework for
benefits (lineage graphs, incremental materialisation, multi-target) that this
project does not use. The runner here is ~60 lines, idempotent, ordered, and
runs in CI in under a second. The decision is recorded in `docs/ARCHITECTURE.md`.

Conventions:

| Prefix | Meaning |
| --- | --- |
| `000_` | extensions and schemas |
| `1xx_stg_` | staging: one view per source table, renamed and typed |
| `2xx_int_` | intermediate: sessionisation, funnel steps, order facts |
| `3xx_mart_` | marts the console and the API read |
| `9xx_` | allow-listed read-only views exposed to the Module 6 copilot |

Every model begins with `DROP VIEW IF EXISTS <name> CASCADE`, then `CREATE
VIEW`. `CREATE OR REPLACE` refuses to insert a column anywhere but the end,
which turns every column addition into a schema fight; models are applied in
dependency order, so the CASCADE only drops views this runner immediately
rebuilds. Re-running is still safe and idempotent. Views are the only
thing in here: anything that needs materialising gets a Prisma migration
instead, so the schema stays in one place.
