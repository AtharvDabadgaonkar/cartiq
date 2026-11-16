#!/usr/bin/env python3
"""Load the committed seed sample into Postgres.

    python scripts/seed.py            # load data/seed/*
    python scripts/seed.py --reset    # clear existing rows first

The seed is what makes `make dev` useful on a clean checkout, with no 44MB
download and no Kaggle account. Its two halves keep their provenance labels:
real rows load as REAL_DATASET, simulated rows as SIMULATED.

See data/seed/manifest.json for exactly what the sample contains and where the
real half came from.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

import pandas as pd  # noqa: E402

from cartiq_api.loaders import (  # noqa: E402
    deterministic_id,
    load_events,
    load_products,
    load_returns,
    psycopg_connection,
    table_counts,
)

SEED_DIR = REPO_ROOT / "data" / "seed"


def _parse_literals(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    """Revive dict/list columns that CSV flattened into their repr."""
    for column in columns:
        if column not in frame.columns:
            continue
        frame[column] = frame[column].map(
            lambda value: (
                value
                if isinstance(value, dict | list)
                else ast.literal_eval(value)
                if isinstance(value, str) and value.strip()
                else {}
            )
        )
    return frame


def main() -> int:
    """Load every seed file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="delete existing rows first"
    )
    args = parser.parse_args()

    manifest_path = SEED_DIR / "manifest.json"
    if not manifest_path.exists():
        print("no seed found. Run `python scripts/build_seed.py` first.")
        return 1

    manifest = json.loads(manifest_path.read_text())
    print(f"real half      {manifest['real']['dataset']}")
    print(f"               {manifest['real']['selection']}")
    print(f"               licence {manifest['real']['licence']}")
    print(
        f"simulated half seed {manifest['simulated']['seed']}, "
        f"{manifest['simulated']['sessions']:,} sessions"
    )

    products = _parse_literals(
        pd.read_csv(SEED_DIR / "products.csv.gz"), ("attributes", "generated_fields")
    )
    real_events = _parse_literals(
        pd.read_csv(SEED_DIR / "events_real.csv.gz", parse_dates=["timestamp"]),
        ("properties", "experiment_assignments"),
    )
    simulated_events = _parse_literals(
        pd.read_csv(SEED_DIR / "events_simulated.csv.gz", parse_dates=["timestamp"]),
        ("properties", "experiment_assignments"),
    )
    returns = pd.read_csv(SEED_DIR / "return_lines.csv.gz", parse_dates=["occurred_at"])

    import_id = deterministic_id("dataset_import", "seed", manifest["real"]["events"])
    run_id = deterministic_id(
        "simulation_run",
        "seed",
        manifest["simulated"]["seed"],
        manifest["simulated"]["sessions"],
    )

    with psycopg_connection() as connection:
        with connection.cursor() as cursor:
            if args.reset:
                cursor.execute(
                    "TRUNCATE events, return_lines, dataset_imports, "
                    "simulation_runs, products RESTART IDENTITY CASCADE"
                )
                print("\nreset: existing rows cleared")

            cursor.execute(
                """
                INSERT INTO dataset_imports (
                    id, source, name, url, licence, attribution, rows_read, rows_loaded,
                    rows_dropped, products_loaded, returns_loaded, observable_steps
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    import_id,
                    "seed-online-retail-ii",
                    manifest["real"]["dataset"],
                    manifest["real"]["url"],
                    manifest["real"]["licence"],
                    manifest["real"]["attribution"],
                    manifest["real"]["events"],
                    manifest["real"]["events"],
                    json.dumps({}),
                    manifest["real"]["products"],
                    manifest["real"]["return_lines"],
                    manifest["real"]["observable_funnel_steps"],
                ),
            )
            cursor.execute(
                """
                INSERT INTO simulation_runs (id, label, seed, params, sessions)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING
                """,
                (
                    run_id,
                    "seed",
                    manifest["simulated"]["seed"],
                    json.dumps(manifest["simulated"]),
                    manifest["simulated"]["sessions"],
                ),
            )
        connection.commit()

        print("\nloading ...")
        print(f"  products    {load_products(connection, products):>8,}")
        print(
            "  events (real)      "
            f"{load_events(connection, real_events, source='REAL_DATASET', key_prefix='seed:real'):>8,}"
        )
        print(
            "  events (simulated) "
            f"{load_events(connection, simulated_events, source='SIMULATED', key_prefix='seed:sim', simulation_run_id=run_id):>8,}"
        )
        print(
            "  return lines       "
            f"{load_returns(connection, returns, dataset_import_id=import_id, key_prefix='seed'):>8,}"
        )

    print("\ntable counts:")
    for table, count in table_counts().items():
        print(f"  {table:<18} {count:>10,}")
    print(f"\nAttribution: {manifest['real']['attribution']}")
    print("Simulated rows are labelled SIMULATED and are not a real-world result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
