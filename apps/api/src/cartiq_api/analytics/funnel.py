"""Journey funnel and step drop-off."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from cartiq_api.analytics.filters import Filters
from cartiq_api.db import get_engine

#: Step order and labels, mirroring packages/shared/src/events.ts FUNNEL_STEPS.
FUNNEL_STEPS: tuple[tuple[str, str], ...] = (
    ("visit", "Visit"),
    ("browse", "Search / Browse"),
    ("product_view", "Product View"),
    ("add_to_cart", "Add to Cart"),
    ("checkout", "Checkout Start"),
    ("shipping", "Shipping"),
    ("payment", "Payment"),
    ("purchase", "Purchase"),
)


def funnel(filters: Filters | None = None) -> pd.DataFrame:
    """Sessions reaching each funnel step, with drop-off between steps.

    Returns one row per step with:
        sessions          sessions that reached this step
        step_rate         share of the PREVIOUS step that advanced
        overall_rate      share of step 0 that reached this step
        dropped           sessions lost between the previous step and this one
        drop_rate         share of the previous step that was lost
    """
    filters = filters or Filters()
    where, params = filters.where("f")

    statement = text(
        f"""
        SELECT f.step_key, f.step_index, f.step_label,
               COUNT(DISTINCT f.session_id) AS sessions
        FROM mart_funnel f
        WHERE {where}
        GROUP BY f.step_key, f.step_index, f.step_label
        ORDER BY f.step_index
        """
    )
    with get_engine().connect() as connection:
        frame = pd.read_sql_query(statement, connection, params=params)

    # A step nobody reached is absent from the result, but it is still a step:
    # showing a seven-row funnel because one stage was empty hides the collapse.
    complete = pd.DataFrame(
        {
            "step_key": [key for key, _ in FUNNEL_STEPS],
            "step_label": [label for _, label in FUNNEL_STEPS],
            "step_index": range(len(FUNNEL_STEPS)),
        }
    )
    frame = complete.merge(frame[["step_key", "sessions"]], on="step_key", how="left")
    # An empty right-hand side makes the merged column object dtype, and
    # fillna on that triggers a deprecated silent downcast. Coerce first.
    frame["sessions"] = pd.to_numeric(frame["sessions"], errors="coerce").fillna(0).astype(int)

    entered = int(frame.loc[frame["step_index"] == 0, "sessions"].iloc[0])
    previous = frame["sessions"].shift(1)

    frame["overall_rate"] = frame["sessions"] / entered if entered else 0.0
    frame["step_rate"] = (frame["sessions"] / previous).fillna(1.0)
    frame["dropped"] = (previous - frame["sessions"]).fillna(0).astype(int)
    frame["drop_rate"] = (frame["dropped"] / previous).fillna(0.0)
    # A step cannot gain sessions; if it appears to, the rate is undefined
    # rather than a lift, so clamp instead of reporting a negative loss.
    frame["drop_rate"] = frame["drop_rate"].clip(lower=0.0)

    return frame


def funnel_by_dimension(dimension: str, filters: Filters | None = None) -> pd.DataFrame:
    """The same funnel, split by one session attribute.

    Args:
        dimension: `device`, `traffic_source`, `segment` or `is_new_user`.
        filters: The slice to split.

    Raises:
        ValueError: If the dimension is not an allow-listed column.
    """
    allowed = {"device", "traffic_source", "segment", "is_new_user"}
    if dimension not in allowed:
        raise ValueError(f"dimension must be one of {sorted(allowed)}, got {dimension!r}")

    filters = filters or Filters()
    where, params = filters.where("f")

    statement = text(
        f"""
        SELECT f.{dimension}::text AS dimension_value,
               f.step_key, f.step_index, f.step_label,
               COUNT(DISTINCT f.session_id) AS sessions
        FROM mart_funnel f
        WHERE {where}
        GROUP BY 1, 2, 3, 4
        ORDER BY 1, 3
        """
    )
    with get_engine().connect() as connection:
        frame = pd.read_sql_query(statement, connection, params=params)

    if frame.empty:
        return frame

    entered = frame[frame["step_index"] == 0].set_index("dimension_value")["sessions"].to_dict()
    frame["entered"] = frame["dimension_value"].map(entered).fillna(0).astype(int)
    frame["overall_rate"] = (frame["sessions"] / frame["entered"]).fillna(0.0)
    return frame
