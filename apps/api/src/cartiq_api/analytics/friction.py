"""Revenue-weighted friction ranking.

Ranks funnel steps by how much revenue the drop at that step plausibly costs,
so the team argues about the biggest leak rather than the most annoying one.

The estimate is deliberately simple and stated out loud: for each step, the
sessions lost there are valued at the revenue per converting session, scaled by
the probability that a session surviving that step would have gone on to
convert. That is an upper bound on recoverable revenue, not a forecast — it
assumes a recovered session behaves like the ones that already got through.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
from sqlalchemy import text

from cartiq_api.analytics.filters import Filters
from cartiq_api.analytics.funnel import funnel
from cartiq_api.db import get_engine


def friction_ranking(filters: Filters | None = None) -> pd.DataFrame:
    """Rank funnel steps by estimated revenue lost at each one.

    Returns one row per transition with:
        dropped                sessions lost entering this step
        drop_rate              share of the previous step lost
        downstream_conversion  P(convert | reached this step)
        revenue_at_risk        dropped x downstream_conversion x revenue/conversion
    """
    filters = filters or Filters()
    frame = funnel(filters)
    if frame.empty or frame["sessions"].iloc[0] == 0:
        return pd.DataFrame()

    purchases = int(frame["sessions"].iloc[-1])
    # Revenue per converting session, from the same slice.
    revenue_per_conversion = _revenue_per_conversion(filters)

    rows: list[dict[str, object]] = []
    for index in range(1, len(frame)):
        step = frame.iloc[index]
        dropped = int(step["dropped"])
        if dropped <= 0:
            continue
        reached_here = int(step["sessions"])
        # P(convert | reached this step). A session lost BEFORE this step would
        # still have had to clear it, so this is the right conditional to use.
        downstream = purchases / reached_here if reached_here else 0.0
        rows.append(
            {
                "step_key": step["step_key"],
                "step_label": step["step_label"],
                "from_label": frame.iloc[index - 1]["step_label"],
                "dropped": dropped,
                "drop_rate": float(step["drop_rate"]),
                "downstream_conversion": downstream,
                "revenue_at_risk": dropped * downstream * revenue_per_conversion,
            }
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    total = result["revenue_at_risk"].sum()
    result["share_of_loss"] = result["revenue_at_risk"] / total if total else 0.0
    return result.sort_values("revenue_at_risk", ascending=False).reset_index(drop=True)


def _revenue_per_conversion(filters: Filters) -> float:
    """Mean revenue of a converting session in this slice."""
    where, params = filters.where("s")
    statement = text(
        f"""
        SELECT COALESCE(AVG(revenue), 0) AS value
        FROM int_sessions s
        WHERE {where} AND converted
        """
    )
    with get_engine().connect() as connection:
        return float(connection.execute(statement, params).scalar() or 0.0)


def friction_by_segment(filters: Filters | None = None) -> pd.DataFrame:
    """The worst step for each segment, so the fix can be targeted.

    A single global ranking hides that mobile and desktop, or new and loyal
    shoppers, often leak in completely different places.
    """
    filters = filters or Filters()
    where, params = filters.where("s")
    with get_engine().connect() as connection:
        segments = [
            row[0]
            for row in connection.execute(
                text(
                    f"SELECT DISTINCT segment FROM int_sessions s "
                    f"WHERE {where} AND segment IS NOT NULL ORDER BY 1"
                ),
                params,
            )
        ]

    rows: list[dict[str, object]] = []
    for segment in segments:
        ranking = friction_ranking(replace(filters, segments=(segment,)))
        if ranking.empty:
            continue
        worst = ranking.iloc[0]
        rows.append(
            {
                "segment": segment,
                "worst_step": worst["step_label"],
                "drop_rate": float(worst["drop_rate"]),
                "revenue_at_risk": float(worst["revenue_at_risk"]),
            }
        )
    return pd.DataFrame(rows).sort_values("revenue_at_risk", ascending=False).reset_index(drop=True)
