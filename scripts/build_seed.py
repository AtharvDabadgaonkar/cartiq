#!/usr/bin/env python3
"""Build the committed seed sample in data/seed/.

    python scripts/build_seed.py

The seed makes the app work on a clean checkout without a 44MB download. It is
a deterministic subset:

  * real events  - the earliest N invoices of Online Retail II, so the slice is
    a genuine, attributable extract of the real dataset (CC BY 4.0), not a
    synthetic imitation of it;
  * products     - exactly the products those invoices reference;
  * simulated events - a small run of the session simulator, so the funnel and
    experiment surfaces have something to show.

Both halves keep their provenance labels, so nothing in the seed can be
mistaken for the other kind of data.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from cartiq_api.catalog import build_catalog  # noqa: E402
from cartiq_api.datasets.online_retail import (  # noqa: E402
    ONLINE_RETAIL_II,
    clean,
    download,
    load_raw,
)
from cartiq_api.simulation import DEFAULT_PARAMS, simulate  # noqa: E402

SEED_DIR = REPO_ROOT / "data" / "seed"
RAW_DIR = REPO_ROOT / "data" / "raw" / ONLINE_RETAIL_II.key


def main() -> int:
    """Write the seed CSVs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--invoices", type=int, default=3000, help="real invoices to include"
    )
    parser.add_argument("--sim-sessions", type=int, default=12_000)
    parser.add_argument("--sim-seed", type=int, default=42)
    args = parser.parse_args()

    SEED_DIR.mkdir(parents=True, exist_ok=True)

    print("reading the real dataset ...")
    result = clean(load_raw(download(RAW_DIR)))

    # Earliest N invoices: deterministic, and keeps whole orders intact so
    # basket-level metrics in the seed are still correct.
    starts = result.events[result.events["event_type"] == "session_start"]
    keep = set(starts.sort_values("timestamp")["session_id"].head(args.invoices))
    real_events = result.events[result.events["session_id"].isin(keep)].copy()

    used_products = set(real_events["product_id"].dropna().unique())
    products = result.products[result.products["product_id"].isin(used_products)]
    catalog = build_catalog(products)
    # Cancellations carry their own invoice numbers ("C489449") and do not
    # reference the order they cancel, so they cannot be matched to the kept
    # invoices. Take the same time window instead, which keeps the slice
    # internally consistent.
    cutoff = real_events["timestamp"].max()
    returns = result.returns[result.returns["occurred_at"] <= cutoff]

    print(f"  real events   {len(real_events):,}")
    print(f"  products      {len(catalog):,}")
    print(f"  return lines  {len(returns):,}")

    print("simulating a small run ...")
    params = replace(DEFAULT_PARAMS, seed=args.sim_seed, sessions=args.sim_sessions)
    simulated = simulate(params, catalog.rename(columns={"product_id": "product_id"}))
    print(f"  simulated events {len(simulated.events):,}")

    real_events.to_csv(SEED_DIR / "events_real.csv.gz", index=False, compression="gzip")
    simulated.events.to_csv(
        SEED_DIR / "events_simulated.csv.gz", index=False, compression="gzip"
    )
    catalog.to_csv(SEED_DIR / "products.csv.gz", index=False, compression="gzip")
    returns.to_csv(SEED_DIR / "return_lines.csv.gz", index=False, compression="gzip")

    manifest = {
        "generated_by": "scripts/build_seed.py",
        "real": {
            "dataset": ONLINE_RETAIL_II.name,
            "url": ONLINE_RETAIL_II.url,
            "licence": ONLINE_RETAIL_II.licence,
            "attribution": ONLINE_RETAIL_II.attribution,
            "selection": f"earliest {args.invoices} invoices, whole orders only",
            "events": int(len(real_events)),
            "products": int(len(catalog)),
            "return_lines": int(len(returns)),
            "observable_funnel_steps": list(ONLINE_RETAIL_II.observable_steps),
        },
        "simulated": {
            "generated_by": "scripts/simulate.py (cartiq_api.simulation)",
            "seed": args.sim_seed,
            "sessions": args.sim_sessions,
            "events": int(len(simulated.events)),
            "documented_in": "docs/SIMULATION.md",
            "truth": simulated.truth,
            "warning": "SIMULATED sessions. Not a real-world result.",
        },
    }
    (SEED_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    total = sum(f.stat().st_size for f in SEED_DIR.glob("*.gz"))
    print(
        f"\nwrote {SEED_DIR.relative_to(REPO_ROOT)} ({total / 1e6:.1f} MB compressed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
