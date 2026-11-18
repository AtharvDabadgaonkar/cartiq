"""The committed snapshot the hosted console reads.

The point of these tests is that the snapshot cannot quietly become fiction.
It is committed data, so nothing stops someone hand-editing a parquet file or
leaving it behind after the SQL changes; the reconciliation test below compares
it against a live query and fails when the two disagree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshot"
sys.path.insert(0, str(REPO_ROOT / "apps" / "console"))

from cartiq_api.analytics import Filters, funnel, kpis  # noqa: E402
from cartiq_api.db import ping  # noqa: E402

pytestmark_snapshot = pytest.mark.skipif(
    not (SNAPSHOT_DIR / "manifest.json").exists(),
    reason="no snapshot committed",
)
pytestmark_db = pytest.mark.skipif(not ping(), reason="no database")


def manifest() -> dict:
    """The committed manifest."""
    return json.loads((SNAPSHOT_DIR / "manifest.json").read_text())


@pytestmark_snapshot
def test_manifest_records_its_own_provenance():
    payload = manifest()
    assert payload["generated_by"] == "scripts/export_snapshot.py"
    assert payload["taken_on"], "a reader has to be able to see how old this is"
    assert payload["sources"], "a snapshot with no sources would render nothing"
    assert payload["row_counts"]["events"] > 0


@pytestmark_snapshot
def test_every_source_has_the_panels_each_page_reads():
    """A missing file renders as an empty panel, which looks like a bug."""
    payload = manifest()
    for source in payload["sources"]:
        for name in (
            "funnel",
            "friction_ranking",
            "segment_kpis",
            "rfm_segments",
        ):
            path = SNAPSHOT_DIR / f"{name}__{source}.parquet"
            assert path.exists(), f"{name} missing for {source}"
        assert (SNAPSHOT_DIR / f"kpis__{source}.json").exists()
        for dimension in ("device", "traffic_source", "segment", "is_new_user"):
            path = SNAPSHOT_DIR / f"funnel_by_dimension__{source}__{dimension}.parquet"
            assert path.exists(), f"{dimension} split missing for {source}"


@pytestmark_snapshot
def test_the_abandonment_export_is_readable_either_way():
    """It carries a result or the reason there is none, never nothing."""
    payload = json.loads((SNAPSHOT_DIR / "abandonment.json").read_text())
    if "error" in payload:
        assert payload["error"]
        return
    assert payload["rows"] > 0
    assert payload["best_model"] in payload["metrics"]
    assert payload["calibration"], "the page plots a reliability curve"
    assert payload["feature_importance"]


@pytestmark_snapshot
def test_cluster_scatter_stays_within_the_plotted_sample():
    """The page plots at most 2,000 points, so the export should not exceed it."""
    for path in SNAPSHOT_DIR.glob("cluster_assigned__*.parquet"):
        frame = pd.read_parquet(path)
        assert len(frame) <= 2_000, path.name
        assert {"cluster", "frequency", "monetary"} <= set(frame.columns)


def _database_holds_the_snapshots_data() -> bool:
    """True when the live database is the one the snapshot was taken from.

    CI seeds its own database and runs its own simulation, so its rows are not
    the rows behind the committed snapshot and comparing the two would fail for
    the wrong reason. The event count identifies the dataset closely enough.
    """
    if not ping():
        return False
    from cartiq_api.db import get_engine
    from sqlalchemy import text

    with get_engine().connect() as connection:
        live = connection.execute(text("SELECT COUNT(*) FROM events")).scalar_one()
    return int(live) == int(manifest()["row_counts"]["events"])


@pytestmark_snapshot
@pytestmark_db
@pytest.mark.skipif(
    not ((SNAPSHOT_DIR / "manifest.json").exists() and _database_holds_the_snapshots_data()),
    reason="the database holds different data than the snapshot was taken from",
)
def test_snapshot_still_agrees_with_a_live_query():
    """The committed numbers must match what the SQL says today.

    This is the test that makes the snapshot trustworthy rather than merely
    old. If the models change and nobody re-exports, this fails and says so.
    It runs on the machine the snapshot came from, which is the machine where
    someone is about to commit a stale one.
    """
    payload = manifest()
    source = payload["sources"][0]
    filters = Filters(data_source=source)

    committed = pd.read_parquet(SNAPSHOT_DIR / f"funnel__{source}.parquet")
    live = funnel(filters)
    assert list(committed["step_key"]) == list(live["step_key"])
    pd.testing.assert_series_equal(
        committed["sessions"].astype("int64"),
        live["sessions"].astype("int64"),
        check_names=False,
    )

    committed_kpis = json.loads((SNAPSHOT_DIR / f"kpis__{source}.json").read_text())
    live_kpis = kpis(filters)
    for key, entry in live_kpis.items():
        assert key in committed_kpis, f"{key} missing from the snapshot"
        # `_context` carries the slice's denominators, not a KPI.
        if key.startswith("_"):
            continue
        if entry["available"] and entry["value"] is not None:
            assert committed_kpis[key]["value"] == pytest.approx(entry["value"], rel=1e-9), key


@pytestmark_snapshot
def test_the_snapshot_is_small_enough_to_commit():
    """A deploy artefact in git should stay a few hundred kilobytes."""
    total = sum(p.stat().st_size for p in SNAPSHOT_DIR.iterdir())
    assert total < 5 * 1_048_576, f"{total / 1_048_576:.1f} MB is too much for git"
