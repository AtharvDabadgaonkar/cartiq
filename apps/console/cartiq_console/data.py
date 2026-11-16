"""Database access for the console.

Read-only by construction: the storefront owns writes through Prisma. Queries
are cached briefly so a page rerun does not hammer a free-tier Postgres.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import text

from cartiq_api.db import get_engine, ping


@st.cache_resource
def engine() -> Any:
    """Process-wide SQLAlchemy engine."""
    return get_engine()


@st.cache_data(ttl=60, show_spinner=False)
def query(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run a read-only query and return a DataFrame."""
    with engine().connect() as connection:
        return pd.read_sql_query(text(sql), connection, params=params or {})


def database_available() -> bool:
    """True when Postgres answers. The console still renders when it does not."""
    return ping()


@st.cache_data(ttl=30, show_spinner=False)
def row_counts() -> dict[str, int]:
    """Counts the console uses to decide whether there is anything to show yet."""
    sql = """
        SELECT
            (SELECT count(*) FROM events)                                     AS events,
            (SELECT count(*) FROM events WHERE source = 'REAL_DATASET')       AS real_events,
            (SELECT count(*) FROM events WHERE source = 'SIMULATED')          AS simulated_events,
            (SELECT count(*) FROM events WHERE source = 'LIVE_DEMO')          AS demo_events,
            (SELECT count(*) FROM products)                                   AS products,
            (SELECT count(*) FROM experiments)                                AS experiments,
            (SELECT count(*) FROM llm_calls)                                  AS llm_calls
    """
    frame = query(sql)
    return {column: int(frame.iloc[0][column]) for column in frame.columns}
