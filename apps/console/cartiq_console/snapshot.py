"""Read a committed snapshot of the analytics, for deployment without a database.

Streamlit Community Cloud runs the console but hosts no Postgres, and a free
hosted database is one more account to keep alive. So `scripts/export_snapshot.py`
runs the real SQL models locally and commits the *results* to `data/snapshot/`;
this module reads them back.

What this is and is not:

* The numbers come from the same SQL and the same model code as the live
  console. Nothing is recomputed here and nothing is hand-written, so the
  hosted figures cannot drift from the warehouse's answer.
* It is a photograph, not a window. The slice is fixed at export time, so the
  date, device and segment filters cannot be honoured — `source.py` hides them
  rather than showing controls that silently do nothing.
* Every page that reads a snapshot says so, with the date it was taken. A
  reader must never mistake it for a live query.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

#: Repository root, four parents up from this file.
REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshot"
MANIFEST = SNAPSHOT_DIR / "manifest.json"


@lru_cache(maxsize=1)
def manifest() -> dict[str, Any] | None:
    """The snapshot's provenance, or None when no snapshot is committed."""
    try:
        return json.loads(MANIFEST.read_text())  # type: ignore[no-any-return]
    except (OSError, ValueError):
        return None


def exists() -> bool:
    """True when a readable snapshot is present."""
    return manifest() is not None


def forced() -> bool:
    """True when the operator asked for snapshot mode explicitly.

    Set `CARTIQ_SNAPSHOT=1` to preview the deployed experience locally while a
    database is running.
    """
    return os.environ.get("CARTIQ_SNAPSHOT", "").strip().lower() in {"1", "true", "yes"}


def taken_on() -> str:
    """Export date as plain text, for the banner."""
    payload = manifest() or {}
    return str(payload.get("taken_on", "an unknown date"))


def sources() -> list[str]:
    """Data sources the snapshot covers."""
    payload = manifest() or {}
    return list(payload.get("sources", []))


@lru_cache(maxsize=64)
def frame(key: str) -> pd.DataFrame | None:
    """Load one exported table, or None when it is not in the snapshot."""
    path = SNAPSHOT_DIR / f"{key}.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:  # noqa: BLE001 - a corrupt file is a missing panel, not a crash
        return None


@lru_cache(maxsize=16)
def payload(key: str) -> dict[str, Any] | None:
    """Load one exported JSON document, or None when absent."""
    path = SNAPSHOT_DIR / f"{key}.json"
    try:
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    except (OSError, ValueError):
        return None
