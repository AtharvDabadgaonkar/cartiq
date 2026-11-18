#!/usr/bin/env python3
"""Export the console's analytics to `data/snapshot/`, for database-free deploys.

Streamlit Community Cloud hosts the console but no Postgres. Rather than
reimplementing the analytics against files -- which would create a second
source of truth that could disagree with the warehouse -- this runs the real
SQL models and the real model code against a live database and commits the
results.

    make snapshot
    python scripts/export_snapshot.py [--sessions-only] [--out data/snapshot]

Every file written is a result, never a hand-typed number, and the manifest
records when it was taken and from which rows, so a reader can check it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(REPO_ROOT / "apps" / "console"))

DEFAULT_OUT = REPO_ROOT / "data" / "snapshot"

#: Dimensions the funnel page offers in its "compare a dimension" selector.
DIMENSIONS = ("device", "traffic_source", "segment", "is_new_user")
#: Cluster counts the segments page's slider allows.
CLUSTER_RANGE = range(2, 7)
#: Points the segments page plots, so the export carries no more than that.
CLUSTER_SCATTER_POINTS = 2_000


def _write_frame(out: Path, key: str, frame: pd.DataFrame) -> int:
    """Write one result table, returning its row count."""
    path = out / f"{key}.parquet"
    # Object columns holding dicts or lists (jsonb) do not survive parquet, so
    # they are serialised to text first.
    safe = frame.copy()
    for column in safe.columns:
        if safe[column].map(lambda v: isinstance(v, (dict, list))).any():
            safe[column] = safe[column].map(
                lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v
            )
    safe.to_parquet(path, index=False, compression="zstd")
    return len(safe)


def _write_json(out: Path, key: str, payload: Any) -> None:
    (out / f"{key}.json").write_text(json.dumps(payload, indent=1, default=str) + "\n")


def _jsonable(value: Any) -> Any:
    """Convert numpy and date scalars so json.dumps does not choke."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def main() -> int:
    """Export every panel the console reads, then write the manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output directory")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="do not clear the directory first (for appending one source)",
    )
    args = parser.parse_args()

    from cartiq_api.analytics import (
        Filters,
        behavioural_clusters,
        friction_ranking,
        funnel,
        funnel_by_dimension,
        kpis,
        rfm_segments,
        segment_kpis,
    )
    from cartiq_api.analytics.friction import friction_by_segment
    from cartiq_api.db import get_engine, ping
    from cartiq_api.ml import train_abandonment_model
    from cartiq_api.ml.abandonment import NotEnoughDataError
    from sqlalchemy import text

    if not ping():
        print("no database. Start one with `make db-up` and load it first.")
        return 1

    out = Path(args.out)
    if out.exists() and not args.keep:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    written: dict[str, int] = {}

    # --- Which sources actually have sessions ------------------------------
    with get_engine().connect() as connection:
        sources = [
            row[0]
            for row in connection.execute(
                text(
                    "SELECT data_source, COUNT(*) n FROM int_sessions "
                    "GROUP BY 1 ORDER BY n DESC"
                )
            )
        ]
    if not sources:
        print("the database has no sessions. Run `make seed` first.")
        return 1
    print(f"sources: {', '.join(sources)}")

    # --- Inventory and provenance ------------------------------------------
    from cartiq_console.data import dataset_imports, row_counts
    from cartiq_console.data import simulation_runs

    # These are Streamlit-cached in normal use; call the undecorated function so
    # the export does not need a script run context.
    counts = {k: int(v) for k, v in row_counts.__wrapped__().items()}
    _write_json(out, "row_counts", counts)

    imports = dataset_imports.__wrapped__()
    written["dataset_imports"] = _write_frame(out, "dataset_imports", imports)
    runs = simulation_runs.__wrapped__()
    written["simulation_runs"] = _write_frame(out, "simulation_runs", runs)

    steps: set[str] = set()
    if not imports.empty:
        for row in imports["observable_steps"]:
            steps.update(row or [])
    _write_json(out, "observable_steps", sorted(steps))
    print(f"inventory: {counts.get('events', 0):,} events")

    # --- Per-source analytics ----------------------------------------------
    for source in sources:
        filters = Filters(data_source=source)
        print(f"\n[{source}]")

        # KPIs are a nested dict (value / available / reason per metric), not a
        # table, so they go out as JSON.
        _write_json(out, f"kpis__{source}", kpis(filters))

        for name, result in (
            ("funnel", funnel(filters)),
            ("friction_ranking", friction_ranking(filters)),
            ("friction_by_segment", friction_by_segment(filters)),
            ("segment_kpis", segment_kpis(source)),
            ("rfm_segments", rfm_segments(source)),
        ):
            key = f"{name}__{source}"
            written[key] = _write_frame(out, key, result)
            print(f"  {name:<20} {written[key]:>7,} rows")

        for dimension in DIMENSIONS:
            key = f"funnel_by_dimension__{source}__{dimension}"
            written[key] = _write_frame(
                out, key, funnel_by_dimension(dimension, filters)
            )
        print(f"  funnel_by_dimension  {len(DIMENSIONS)} dimensions")

        for k in CLUSTER_RANGE:
            try:
                assigned, profile = behavioural_clusters(source, k=k)
            except Exception as error:  # noqa: BLE001 - too few customers is normal
                print(f"  clusters k={k} skipped ({type(error).__name__})")
                continue
            key = f"cluster_profile__{source}__k{k}"
            written[key] = _write_frame(out, key, profile)
            # The page scatter-plots the assignments but samples 2,000 points
            # first, so only that sample is worth committing -- taken with the
            # same seed, so the hosted chart shows the same points.
            sample = assigned.sample(
                min(len(assigned), CLUSTER_SCATTER_POINTS), random_state=42
            )
            key = f"cluster_assigned__{source}__k{k}"
            written[key] = _write_frame(
                out, key, sample[["cluster", "frequency", "monetary", "recency_days"]]
            )
        print(
            f"  cluster_profile      k={CLUSTER_RANGE.start}..{CLUSTER_RANGE.stop - 1}"
        )

    # --- The abandonment model ---------------------------------------------
    try:
        result = train_abandonment_model()
        _write_json(
            out,
            "abandonment",
            {
                "rows": result.rows,
                "positive_rate": result.positive_rate,
                "best_model": result.best_model,
                "metrics": result.metrics,
                "calibration": result.calibration.to_dict(orient="records"),
                "feature_importance": result.feature_importance.to_dict(
                    orient="records"
                ),
            },
        )
        print(f"\nabandonment model: {result.best_model} on {result.rows:,} carts")
    except NotEnoughDataError as error:
        # Recorded, not skipped: the page must be able to say why it is empty
        # rather than looking broken.
        _write_json(out, "abandonment", {"error": str(error)})
        print(f"\nabandonment model: not enough data ({error})")

    # --- Manifest -----------------------------------------------------------
    taken = datetime.now(timezone.utc)
    _write_json(
        out,
        "manifest",
        {
            "generated_by": "scripts/export_snapshot.py",
            "taken_on": taken.date().isoformat(),
            "taken_at": taken.isoformat(timespec="seconds"),
            "sources": sources,
            "row_counts": counts,
            "tables": {k: v for k, v in sorted(written.items())},
            "note": (
                "Results of the live SQL models and model code, exported for a "
                "deployment with no database. Not a reimplementation: the same "
                "queries produced these numbers. The slice is frozen at export "
                "time, so the console hides the date and dimension filters when "
                "reading this."
            ),
        },
    )

    size = sum(p.stat().st_size for p in out.iterdir())
    print(f"\n{len(list(out.iterdir()))} files, {size / 1_048_576:.1f} MB in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
