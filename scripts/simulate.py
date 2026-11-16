#!/usr/bin/env python3
"""Generate reproducible simulated shopper sessions.

    python scripts/simulate.py                       # defaults (see SIMULATION.md)
    python scripts/simulate.py --sessions 120000     # smaller, for a free-tier demo
    python scripts/simulate.py --seed 7 --label aa --aa-test

Why this exists: the real dataset contains no experiment, so there is no
treatment group to measure. These sessions are generated from explicit,
documented behavioural parameters, written with `source = 'SIMULATED'`, and
labelled as simulated everywhere they surface.

The configured effect is not a secret — it is in docs/SIMULATION.md and on the
`simulation_runs` row. The point is that the Experiment Studio never reads it:
it has to recover the effect from the events alone.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from cartiq_api.config import get_settings  # noqa: E402
from cartiq_api.db import get_engine  # noqa: E402
from cartiq_api.loaders import (  # noqa: E402
    deterministic_id,
    load_events,
    psycopg_connection,
    table_counts,
)
from cartiq_api.simulation import DEFAULT_PARAMS, simulate  # noqa: E402
from cartiq_api.simulation.params import InterventionParams  # noqa: E402


def load_catalog() -> pd.DataFrame:
    """Real products, so simulated carts hold real items at real prices."""
    statement = text(
        """
        SELECT p.id AS product_id, p.price::float8 AS price,
               COALESCE(SUM(e.quantity), 1) AS units_sold
        FROM products p
        LEFT JOIN events e
          ON e.product_id = p.id AND e.event_type = 'purchase'
        GROUP BY p.id, p.price
        """
    )
    with get_engine().connect() as connection:
        return pd.read_sql_query(statement, connection)


def git_sha() -> str | None:
    """Commit the run was produced at."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main() -> int:
    """Simulate sessions and load them into Postgres."""
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=settings.sim_seed)
    parser.add_argument("--sessions", type=int, default=DEFAULT_PARAMS.sessions)
    parser.add_argument("--label", default="flagship")
    parser.add_argument(
        "--aa-test",
        action="store_true",
        help="zero every treatment effect, for the A/A false-positive check",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="simulate and report, load nothing"
    )
    parser.add_argument(
        "--no-catalog", action="store_true", help="use synthetic products"
    )
    args = parser.parse_args()

    params = replace(DEFAULT_PARAMS, seed=args.seed, sessions=args.sessions)
    if args.aa_test:
        params = replace(
            params,
            interventions={
                key: InterventionParams(
                    key=intervention.key,
                    description=intervention.description,
                    effects=dict.fromkeys(intervention.effects, 1.0),
                    eligible_devices=intervention.eligible_devices,
                    guardrail_effects=dict.fromkeys(
                        intervention.guardrail_effects, 1.0
                    ),
                )
                for key, intervention in params.interventions.items()
            },
        )

    catalog = None if args.no_catalog else load_catalog()
    if catalog is not None and catalog.empty:
        print(
            "no catalog in the database; run `make ingest` first, or pass --no-catalog"
        )
        return 1

    print(f"seed      {params.seed}")
    print(f"sessions  {params.sessions:,}")
    print(f"label     {args.label}{' (A/A)' if args.aa_test else ''}")
    print(f"catalog   {0 if catalog is None else len(catalog):,} real products")
    print("\nsimulating ...")
    output = simulate(params, catalog)

    sessions = output.sessions
    print(f"events          {len(output.events):,}")
    print(f"sessions        {len(sessions):,}")
    print(f"conversion      {sessions['converted'].mean():.4%}")
    print("\nper variant:")
    variant_column = f"variant_{params.experiments[0].key}"
    summary = sessions.groupby(variant_column).agg(
        sessions=("converted", "size"),
        conversions=("converted", "sum"),
        conversion_rate=("converted", "mean"),
    )
    for variant, row in summary.iterrows():
        print(
            f"  {variant:<10} {int(row.sessions):>8,} sessions  "
            f"{int(row.conversions):>6,} conversions  {row.conversion_rate:.4%}"
        )

    print("\nconfigured ground truth (documented, never read by the stats engine):")
    for key, value in output.truth.items():
        print(f"  {key:<34} {value:.6f}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    run_id = deterministic_id(
        "simulation_run", args.label, params.seed, params.sessions
    )
    print("\nloading into Postgres ...")
    with psycopg_connection() as connection:
        with connection.cursor() as cursor:
            # A re-run with the same label/seed/size replaces its own events.
            cursor.execute("DELETE FROM events WHERE simulation_run_id = %s", (run_id,))
            cursor.execute("DELETE FROM simulation_runs WHERE id = %s", (run_id,))
            cursor.execute(
                """
                INSERT INTO simulation_runs (id, label, seed, params, sessions, git_sha)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    args.label + ("_aa" if args.aa_test else ""),
                    params.seed,
                    json.dumps(
                        {"params": params.to_dict(), "truth": output.truth}, default=str
                    ),
                    params.sessions,
                    git_sha(),
                ),
            )
        connection.commit()

        loaded = load_events(
            connection,
            output.events,
            source="SIMULATED",
            key_prefix=f"sim:{args.label}:{params.seed}",
            simulation_run_id=run_id,
        )
        print(f"  events  {loaded:>10,} inserted")

    print("\ntable counts:")
    for table, count in table_counts().items():
        print(f"  {table:<18} {count:>10,}")
    print("\nThese sessions are SIMULATED. Every number derived from them is labelled")
    print("as such in the console, the README and the experiment readout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
