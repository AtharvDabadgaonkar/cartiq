#!/usr/bin/env python3
"""Apply the versioned SQL models in /models, in filename order.

Idempotent: every model is CREATE OR REPLACE, so this can run on every deploy.
Run with `make migrate` (after Prisma migrations) or directly:

    python scripts/build_models.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "models"
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))


def model_files() -> list[Path]:
    """Return the SQL models in deterministic application order."""
    return sorted(MODELS_DIR.glob("*.sql"))


def main() -> int:
    """Apply every model, printing one line each."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="list models without applying them"
    )
    args = parser.parse_args()

    files = model_files()
    if not files:
        print("no models found in /models")
        return 0

    if args.dry_run:
        for path in files:
            print(f"would apply {path.name}")
        return 0

    from sqlalchemy import text  # imported late so --dry-run needs no deps

    from cartiq_api.db import get_engine

    engine = get_engine()
    with engine.begin() as connection:
        for path in files:
            connection.execute(text(path.read_text()))
            print(f"applied {path.name}")
    print(f"{len(files)} model(s) applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
