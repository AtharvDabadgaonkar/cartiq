"""One place that decides where a page's numbers come from.

The console runs in two modes:

live
    A reachable Postgres with the SQL models built. Every function here is a
    thin pass-through to `cartiq_api.analytics`, and the filters work.

snapshot
    No database, so results exported by `scripts/export_snapshot.py` are read
    from `data/snapshot/`. The figures are identical to what the live console
    showed when the snapshot was taken, because they were produced by that same
    code -- but the slice is frozen, so only the data-source selector is
    offered and the page says what it is reading.

Pages import from here rather than from `cartiq_api.analytics` directly, so
neither mode is a special case inside page code.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

from cartiq_api.analytics import Filters
from cartiq_console import snapshot
from cartiq_console.data import database_available

#: Clusters the snapshot exports a profile for, matching the page's slider.
SNAPSHOT_CLUSTER_RANGE = range(2, 7)

_EMPTY = pd.DataFrame()


@st.cache_data(ttl=30, show_spinner=False)
def _reachable() -> bool:
    """Whether Postgres answers, remembered briefly.

    Streamlit reruns the script on every interaction, and an unreachable
    database would otherwise cost a refused TCP connection per rerun. The short
    TTL still lets a database started after the console appear without a
    restart.
    """
    return database_available()


def mode() -> str:
    """Either "live" or "snapshot" or "none"."""
    if snapshot.forced() and snapshot.exists():
        return "snapshot"
    # On a deployment with no DATABASE_URL secret, the settings default points
    # at localhost and cannot be right. Reading the snapshot directly skips a
    # connection attempt that can only fail.
    if not os.environ.get("DATABASE_URL") and snapshot.exists():
        return "snapshot"
    if _reachable():
        return "live"
    return "snapshot" if snapshot.exists() else "none"


def is_snapshot() -> bool:
    """True when pages should read the committed snapshot."""
    return mode() == "snapshot"


def _key(name: str, data_source: str, *extra: Any) -> str:
    parts = [name, data_source, *(str(item) for item in extra)]
    return "__".join(parts)


def _frame(name: str, data_source: str, *extra: Any) -> pd.DataFrame:
    return _or_empty(snapshot.frame(_key(name, data_source, *extra)))


def _or_empty(frame: pd.DataFrame | None) -> pd.DataFrame:
    """A missing panel becomes an empty frame.

    Written out because `frame or _EMPTY` raises: a DataFrame has no truth
    value, so the fallback has to test for None explicitly.
    """
    return _EMPTY if frame is None else frame


# --- Inventory and provenance ---------------------------------------------


def available_sources() -> list[str]:
    """Sources with sessions, from whichever backing store is in use."""
    if is_snapshot():
        return snapshot.sources()
    from cartiq_console.controls import available_sources as live_sources

    return live_sources()


def row_counts() -> dict[str, int]:
    """Inventory counts for the overview page."""
    if is_snapshot():
        payload = snapshot.payload("row_counts") or {}
        return {str(k): int(v) for k, v in payload.items()}
    from cartiq_console.data import row_counts as live_counts

    return live_counts()


def dataset_imports() -> pd.DataFrame:
    """Real-dataset provenance rows."""
    if is_snapshot():
        return _or_empty(snapshot.frame("dataset_imports"))
    from cartiq_console.data import dataset_imports as live_imports

    return live_imports()


def simulation_runs() -> pd.DataFrame:
    """Simulation-run provenance rows."""
    if is_snapshot():
        return _or_empty(snapshot.frame("simulation_runs"))
    from cartiq_console.data import simulation_runs as live_runs

    return live_runs()


def observable_steps() -> set[str]:
    """Funnel steps the loaded real dataset can actually observe."""
    if is_snapshot():
        return set(snapshot.payload("observable_steps") or [])
    from cartiq_console.data import observable_steps as live_steps

    return live_steps()


# --- Funnel and friction ---------------------------------------------------


def funnel(filters: Filters) -> pd.DataFrame:
    """Sessions reaching each funnel step."""
    if is_snapshot():
        return _frame("funnel", filters.data_source)
    from cartiq_api.analytics import funnel as live

    return live(filters)


def kpis(filters: Filters) -> dict[str, dict[str, Any]]:
    """Every KPI for the slice, each with its value and availability."""
    if is_snapshot():
        return snapshot.payload(_key("kpis", filters.data_source)) or {}
    from cartiq_api.analytics import kpis as live

    return live(filters)


def funnel_by_dimension(dimension: str, filters: Filters) -> pd.DataFrame:
    """Funnel split by one dimension."""
    if is_snapshot():
        return _frame("funnel_by_dimension", filters.data_source, dimension)
    from cartiq_api.analytics import funnel_by_dimension as live

    return live(dimension, filters)


def friction_ranking(filters: Filters) -> pd.DataFrame:
    """Revenue-weighted friction ranking."""
    if is_snapshot():
        return _frame("friction_ranking", filters.data_source)
    from cartiq_api.analytics import friction_ranking as live

    return live(filters)


def friction_by_segment(filters: Filters) -> pd.DataFrame:
    """Friction broken out by segment."""
    if is_snapshot():
        return _frame("friction_by_segment", filters.data_source)
    from cartiq_api.analytics.friction import friction_by_segment as live

    return live(filters)


# --- Segmentation ----------------------------------------------------------


def segment_kpis(data_source: str) -> pd.DataFrame:
    """Size and value of each RFM segment."""
    if is_snapshot():
        return _frame("segment_kpis", data_source)
    from cartiq_api.analytics import segment_kpis as live

    return live(data_source)


def rfm_segments(data_source: str) -> pd.DataFrame:
    """Customers with their RFM scores."""
    if is_snapshot():
        return _frame("rfm_segments", data_source)
    from cartiq_api.analytics import rfm_segments as live

    return live(data_source)


def behavioural_clusters(
    data_source: str, k: int = 4
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """K-means cluster assignments and their profile.

    The snapshot carries the profile plus the 2,000-point sample the page
    actually plots, not every assignment: the scatter is capped at that, so
    committing the full per-customer frame once per k would store tens of
    thousands of rows nothing reads.
    """
    if is_snapshot():
        return (
            _frame("cluster_assigned", data_source, f"k{k}"),
            _frame("cluster_profile", data_source, f"k{k}"),
        )
    from cartiq_api.analytics import behavioural_clusters as live

    return live(data_source, k=k)


# --- Abandonment -----------------------------------------------------------


def abandonment_payload() -> dict[str, Any] | None:
    """The exported training result, or None when not in the snapshot."""
    return snapshot.payload("abandonment")
