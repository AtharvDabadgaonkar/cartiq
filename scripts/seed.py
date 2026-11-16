#!/usr/bin/env python3
"""Load the committed seed sample (data/seed) into Postgres.

Not implemented yet — lands in Phase 2. The entrypoint exists from Phase 1
so `make seed` fails with an explanation rather
than a missing-file error.
"""

from __future__ import annotations


def main() -> int:
    """Explain that this script lands in Phase 2."""
    print(
        "seed.py is not implemented yet.\n"
        "It lands in Phase 2 (data: ingestion, seed sample, catalog build, simulator).\n"
        "See docs/SIMULATION.md and the build phases in README.md."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
