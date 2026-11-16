#!/usr/bin/env python3
"""Load a real public e-commerce dataset into Postgres.

    python scripts/ingest.py                      # Online Retail II, full file
    python scripts/ingest.py --limit 200000       # a slice, for a quick run
    python scripts/ingest.py --source rees46      # richer funnel, manual download

Default source is **Online Retail II** (UCI, CC BY 4.0), which downloads without
credentials so `make ingest` produces real data on a clean checkout.

Every run records a `dataset_imports` row holding the source, licence,
attribution, file checksum, what was dropped and why, and which funnel steps the
source can actually observe. Nothing in the console reports a number without
being able to point back at one of those rows.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from cartiq_api.catalog import build_catalog, coverage_report  # noqa: E402
from cartiq_api.datasets import DATASETS  # noqa: E402
from cartiq_api.datasets.base import sha256_of  # noqa: E402
from cartiq_api.datasets.online_retail import (  # noqa: E402
    ONLINE_RETAIL_II,
    clean,
    download,
    load_raw,
)
from cartiq_api.loaders import (  # noqa: E402
    deterministic_id,
    load_events,
    load_products,
    load_returns,
    psycopg_connection,
    table_counts,
)

RAW_DIR = REPO_ROOT / "data" / "raw"


def git_sha() -> str | None:
    """Commit the import was produced at."""
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
    """Download, clean and load the selected dataset."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", default=ONLINE_RETAIL_II.key, choices=sorted(DATASETS)
    )
    parser.add_argument("--limit", type=int, default=None, help="cap source rows read")
    parser.add_argument(
        "--dry-run", action="store_true", help="clean and report, load nothing"
    )
    args = parser.parse_args()

    meta = DATASETS[args.source]
    print(f"source     {meta.name}")
    print(f"licence    {meta.licence}")
    print(f"url        {meta.url}")

    dest = RAW_DIR / meta.key
    if not meta.auto_downloadable:
        print(f"\n{meta.manual_download_note}")
        return 1

    print("\ndownloading (cached after the first run) ...")
    path = download(dest)
    checksum = sha256_of(path)
    print(f"file       {path.relative_to(REPO_ROOT)}  sha256={checksum[:16]}...")

    print("parsing ...")
    raw = load_raw(path, limit=args.limit)
    result = clean(raw)
    catalog = build_catalog(result.products)

    print(f"\nrows read          {result.rows_read:,}")
    for reason, count in sorted(result.dropped.items()):
        print(f"  dropped {reason:<22} {count:>9,}")
    print(f"  returns{'':<23} {len(result.returns):>9,}")
    print(f"events built       {result.rows_loaded:,}")
    print(f"products built     {len(catalog):,}")
    print(f"reconciles         {result.reconciles()}")

    if not result.reconciles():
        print("\nERROR: row counts do not reconcile against the source file.")
        return 1

    print("\ncatalog field coverage (what the source actually carries):")
    for field, share in coverage_report(catalog).items():
        print(f"  {field:<20} {share:>7.1%}")

    print(
        f"\nfunnel steps observable from this source: {', '.join(meta.observable_steps)}"
    )
    print("  steps above `purchase` need behavioural events this source lacks;")
    print(
        "  the console reports them as unmeasurable here and uses simulated sessions."
    )

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    import_id = deterministic_id(
        "dataset_import", meta.key, checksum, args.limit or "full"
    )
    print("\nloading into Postgres ...")
    with psycopg_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO dataset_imports (
                    id, source, name, url, licence, attribution, checksum,
                    rows_read, rows_loaded, rows_dropped, products_loaded,
                    returns_loaded, observable_steps, git_sha
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET created_at = now()
                """,
                (
                    import_id,
                    meta.key,
                    meta.name,
                    meta.url,
                    meta.licence,
                    meta.attribution,
                    checksum,
                    result.rows_read,
                    result.rows_loaded,
                    json.dumps(result.dropped),
                    len(catalog),
                    len(result.returns),
                    list(meta.observable_steps),
                    git_sha(),
                ),
            )
        connection.commit()

        products_loaded = load_products(connection, catalog)
        print(f"  products      {products_loaded:>9,} inserted")
        events_loaded = load_events(
            connection, result.events, source="REAL_DATASET", key_prefix=meta.key
        )
        print(f"  events        {events_loaded:>9,} inserted")
        returns_loaded = load_returns(
            connection, result.returns, dataset_import_id=import_id, key_prefix=meta.key
        )
        print(f"  return_lines  {returns_loaded:>9,} inserted")

    print("\ntable counts:")
    for table, count in table_counts().items():
        print(f"  {table:<18} {count:>9,}")
    print("\nAttribution (also recorded in dataset_imports):")
    print(f"  {meta.attribution}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
