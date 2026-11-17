"""Shared sidebar controls for the diagnosis pages."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import text

from cartiq_api.analytics import Filters
from cartiq_console.data import engine

SOURCE_LABELS = {
    "SIMULATED": "Simulated sessions",
    "REAL_DATASET": "Real dataset",
    "LIVE_DEMO": "Demo storefront traffic",
}

SOURCE_BADGE = {"SIMULATED": "simulated", "REAL_DATASET": "real", "LIVE_DEMO": "demo"}


@st.cache_data(ttl=120, show_spinner=False)
def slice_options(data_source: str) -> dict[str, Any]:
    """Distinct dimension values actually present for a source."""
    statement = text(
        """
        SELECT
            ARRAY(SELECT DISTINCT device FROM int_sessions
                  WHERE data_source = :s AND device IS NOT NULL ORDER BY 1)        AS devices,
            ARRAY(SELECT DISTINCT traffic_source FROM int_sessions
                  WHERE data_source = :s AND traffic_source IS NOT NULL ORDER BY 1) AS sources,
            ARRAY(SELECT DISTINCT segment FROM int_sessions
                  WHERE data_source = :s AND segment IS NOT NULL ORDER BY 1)        AS segments,
            (SELECT MIN(session_date) FROM int_sessions WHERE data_source = :s)     AS min_date,
            (SELECT MAX(session_date) FROM int_sessions WHERE data_source = :s)     AS max_date
        """
    )
    with engine().connect() as connection:
        row = connection.execute(statement, {"s": data_source}).mappings().one()
    return {key: row[key] for key in row}


@st.cache_data(ttl=120, show_spinner=False)
def available_sources() -> list[str]:
    """Sources that actually have sessions loaded, most data first."""
    statement = text(
        "SELECT data_source, COUNT(*) n FROM int_sessions GROUP BY 1 ORDER BY n DESC"
    )
    with engine().connect() as connection:
        return [row[0] for row in connection.execute(statement)]


def filter_sidebar(*, funnel_only: bool = False, key: str = "f") -> Filters:
    """Render the slice controls and return the resulting Filters.

    Args:
        funnel_only: Offer only sources that can express a funnel. A
            transactional import cannot, and letting someone pick it for a
            funnel chart would produce a 100% conversion rate that looks real.
        key: Widget key prefix, so two pages do not share state.
    """
    sources = available_sources()
    if funnel_only:
        sources = [s for s in sources if s in ("SIMULATED", "LIVE_DEMO")] or sources

    with st.sidebar:
        st.markdown("### Slice")
        data_source = st.selectbox(
            "Data source",
            sources,
            format_func=lambda s: SOURCE_LABELS.get(s, s),
            key=f"{key}_source",
            help=(
                "Real and simulated sessions are never mixed in one number. "
                "Switching this switches the whole page."
            ),
        )

        options = slice_options(data_source)
        min_date: date | None = options["min_date"]
        max_date: date | None = options["max_date"]

        date_from: date | None = None
        date_to: date | None = None
        if min_date and max_date and min_date < max_date:
            picked = st.date_input(
                "Date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key=f"{key}_dates",
            )
            # st.date_input returns a tuple once both ends are chosen, and a
            # single date while the user is mid-selection.
            if isinstance(picked, tuple) and len(picked) == 2:
                date_from, date_to = picked[0], picked[1]

        devices = st.multiselect("Device", options["devices"], key=f"{key}_device")
        traffic = st.multiselect(
            "Traffic source", options["sources"], key=f"{key}_traffic"
        )
        segments = st.multiselect("Segment", options["segments"], key=f"{key}_segment")
        visitor = st.radio(
            "Visitor",
            ["All", "New", "Returning"],
            horizontal=True,
            key=f"{key}_visitor",
        )

    return Filters(
        data_source=data_source,
        date_from=date_from,
        date_to=date_to,
        devices=tuple(devices),
        traffic_sources=tuple(traffic),
        segments=tuple(segments),
        is_new_user={"All": None, "New": True, "Returning": False}[visitor],
    )


def format_value(value: float | None, unit: str) -> str:
    """Render a KPI for display."""
    if value is None:
        return "—"
    if unit == "share":
        return f"{value:.2%}"
    if unit == "currency":
        return f"£{value:,.2f}"
    if unit == "count":
        return f"{value:,.2f}" if value % 1 else f"{int(value):,}"
    return str(value)


def empty_state(message: str) -> None:
    """Consistent treatment for a slice with nothing in it."""
    st.info(message, icon=":material/filter_alt_off:")


def as_percent_frame(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Copy of a frame with the named columns rendered as percentages."""
    out = frame.copy()
    for column in columns:
        out[column] = out[column].map(lambda v: f"{v:.1%}" if pd.notna(v) else "—")
    return out
