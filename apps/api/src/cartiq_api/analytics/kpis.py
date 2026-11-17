"""Headline KPIs, with explicit rules about which sources can support them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import text

from cartiq_api.analytics.filters import FUNNEL_CAPABLE_SOURCES, Filters
from cartiq_api.db import get_engine


@dataclass(frozen=True)
class KpiDefinition:
    """What a KPI means and when it is meaningful.

    `requires_sessions` is the important flag. A transactional import contains
    only completed orders, so any metric with sessions in the denominator —
    conversion rate, revenue per visitor, cart abandonment — is 100% or
    undefined by construction there. Reporting it anyway would be the most
    plausible-looking wrong number in the whole project.
    """

    key: str
    label: str
    definition: str
    unit: str
    requires_sessions: bool
    lower_is_better: bool = False


KPI_DEFINITIONS: tuple[KpiDefinition, ...] = (
    KpiDefinition(
        "conversion_rate",
        "Conversion rate",
        "Sessions that reached purchase, divided by all sessions.",
        "share",
        requires_sessions=True,
    ),
    KpiDefinition(
        "aov",
        "Average order value",
        "Total revenue divided by the number of orders.",
        "currency",
        requires_sessions=False,
    ),
    KpiDefinition(
        "revenue_per_visitor",
        "Revenue per visitor",
        "Total revenue divided by all sessions, converting or not.",
        "currency",
        requires_sessions=True,
    ),
    KpiDefinition(
        "cart_abandonment_rate",
        "Cart abandonment rate",
        "Sessions that added to cart but never purchased, divided by sessions that added to cart.",
        "share",
        requires_sessions=True,
        lower_is_better=True,
    ),
    KpiDefinition(
        "search_to_purchase_rate",
        "Search-to-purchase rate",
        "Sessions that used search AND purchased, divided by sessions that used search.",
        "share",
        requires_sessions=True,
    ),
    KpiDefinition(
        "orders",
        "Orders",
        "Distinct orders placed.",
        "count",
        requires_sessions=False,
    ),
    KpiDefinition(
        "revenue",
        "Revenue",
        "Total order revenue.",
        "currency",
        requires_sessions=False,
    ),
    KpiDefinition(
        "items_per_order",
        "Items per order",
        "Total items divided by the number of orders.",
        "count",
        requires_sessions=False,
    ),
    KpiDefinition(
        "clv_historical",
        "Customer lifetime value",
        "Mean observed revenue per attributed customer to date. Historical, not projected.",
        "currency",
        requires_sessions=False,
    ),
)

KPIS_BY_KEY: dict[str, KpiDefinition] = {k.key: k for k in KPI_DEFINITIONS}


def kpis(filters: Filters | None = None) -> dict[str, dict[str, Any]]:
    """Compute every KPI for a slice.

    Each entry carries `value`, `available` and, when unavailable, `reason`.
    A KPI that cannot be computed honestly from the chosen source returns
    `available: False` rather than a misleading number.
    """
    filters = filters or Filters()
    where, params = filters.where("s")
    sessions_meaningful = filters.data_source in FUNNEL_CAPABLE_SOURCES

    session_sql = text(
        f"""
        SELECT
            COUNT(*)                                             AS sessions,
            COUNT(*) FILTER (WHERE converted)                    AS converted_sessions,
            COUNT(*) FILTER (WHERE reached_add_to_cart)          AS carting_sessions,
            COUNT(*) FILTER (WHERE abandoned_cart)               AS abandoned_sessions,
            COUNT(*) FILTER (WHERE used_search)                  AS searching_sessions,
            COUNT(*) FILTER (WHERE used_search AND converted)    AS searching_converted,
            COALESCE(SUM(revenue), 0)                            AS revenue,
            COALESCE(SUM(items_purchased), 0)                    AS items
        FROM int_sessions s
        WHERE {where}
        """
    )
    order_sql = text(
        f"""
        SELECT COUNT(*) AS orders, COALESCE(AVG(revenue), 0) AS aov
        FROM int_orders o
        WHERE o.data_source::text = :data_source
          AND o.session_id IN (SELECT session_id FROM int_sessions s WHERE {where})
        """
    )
    clv_sql = text(
        """
        SELECT COALESCE(AVG(clv_historical), 0) AS clv, COUNT(*) AS customers
        FROM mart_customers WHERE data_source::text = :data_source
        """
    )

    with get_engine().connect() as connection:
        session_row = connection.execute(session_sql, params).mappings().one()
        order_row = connection.execute(order_sql, params).mappings().one()
        clv_row = connection.execute(clv_sql, {"data_source": filters.data_source}).mappings().one()

    sessions = int(session_row["sessions"])
    orders = int(order_row["orders"])
    revenue = float(session_row["revenue"])

    def ratio(numerator: float, denominator: float) -> float | None:
        return numerator / denominator if denominator else None

    raw: dict[str, float | None] = {
        "conversion_rate": ratio(int(session_row["converted_sessions"]), sessions),
        "aov": float(order_row["aov"]) if orders else None,
        "revenue_per_visitor": ratio(revenue, sessions),
        "cart_abandonment_rate": ratio(
            int(session_row["abandoned_sessions"]), int(session_row["carting_sessions"])
        ),
        "search_to_purchase_rate": ratio(
            int(session_row["searching_converted"]), int(session_row["searching_sessions"])
        ),
        "orders": float(orders),
        "revenue": revenue,
        "items_per_order": ratio(float(session_row["items"]), orders),
        "clv_historical": float(clv_row["clv"]) if int(clv_row["customers"]) else None,
    }

    unavailable_reason = (
        "This source records completed orders only, so every session in it converted "
        "by construction. A session-denominated rate computed here would be 100% or "
        "undefined, not a finding."
    )

    out: dict[str, dict[str, Any]] = {}
    for definition in KPI_DEFINITIONS:
        value = raw[definition.key]
        blocked = definition.requires_sessions and not sessions_meaningful
        entry: dict[str, Any] = {
            "label": definition.label,
            "definition": definition.definition,
            "unit": definition.unit,
            "lower_is_better": definition.lower_is_better,
            "available": not blocked and value is not None,
            "value": None if blocked else value,
        }
        if blocked:
            entry["reason"] = unavailable_reason
        elif value is None:
            entry["reason"] = "No sessions matched this slice."
        out[definition.key] = entry

    out["_context"] = {
        "sessions": sessions,
        "orders": orders,
        "slice": filters.describe(),
        "sessions_meaningful": sessions_meaningful,
    }
    return out


def kpi_trend(metric: str, filters: Filters | None = None) -> pd.DataFrame:
    """Daily series for one session-denominated metric."""
    allowed = {"conversion_rate", "revenue", "sessions", "orders"}
    if metric not in allowed:
        raise ValueError(f"metric must be one of {sorted(allowed)}, got {metric!r}")

    filters = filters or Filters()
    where, params = filters.where("s")
    statement = text(
        f"""
        SELECT session_date AS day,
               COUNT(*)                          AS sessions,
               COUNT(*) FILTER (WHERE converted) AS orders,
               COALESCE(SUM(revenue), 0)         AS revenue
        FROM int_sessions s
        WHERE {where}
        GROUP BY session_date
        ORDER BY session_date
        """
    )
    with get_engine().connect() as connection:
        frame = pd.read_sql_query(statement, connection, params=params)

    if frame.empty:
        return frame
    frame["conversion_rate"] = frame["orders"] / frame["sessions"].replace(0, pd.NA)
    return frame[["day", metric]].rename(columns={metric: "value"})
