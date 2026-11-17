"""Customer segmentation: RFM and behavioural clusters."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# scikit-learn ships no py.typed marker, so these are untyped to mypy.
from sklearn.cluster import KMeans  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]
from sqlalchemy import text

from cartiq_api.db import get_engine


@dataclass(frozen=True)
class RfmSegment:
    """A named RFM segment and what it means in business terms."""

    key: str
    label: str
    description: str
    action: str


RFM_SEGMENTS: tuple[RfmSegment, ...] = (
    RfmSegment(
        "champions",
        "Champions",
        "Bought recently, buy often, and spend the most.",
        "Protect them. They are the group a pricing or delivery change hurts most.",
    ),
    RfmSegment(
        "loyal",
        "Loyal",
        "Buy regularly and spend above average, though not the very top.",
        "Grow basket size; they already trust the shop.",
    ),
    RfmSegment(
        "potential_loyalist",
        "Potential loyalist",
        "Recent buyers with a couple of orders and decent spend.",
        "Push the second or third order; this is where loyalty is won.",
    ),
    RfmSegment(
        "new_customers",
        "New customers",
        "Bought very recently, but only once.",
        "Onboard them. A good second experience decides whether they return.",
    ),
    RfmSegment(
        "at_risk",
        "At risk",
        "Used to buy often and spend well, but have not been back for a while.",
        "Win them back before the gap becomes permanent; highest revenue at stake.",
    ),
    RfmSegment(
        "cant_lose",
        "Can't lose them",
        "The biggest spenders of all, now gone quiet.",
        "Human outreach, not a discount email. Losing one of these is material.",
    ),
    RfmSegment(
        "hibernating",
        "Hibernating",
        "Low spend, low frequency, and a long time since the last order.",
        "Cheap reactivation only; do not spend acquisition money here.",
    ),
    RfmSegment(
        "lost",
        "Lost",
        "Lowest recency, frequency and spend.",
        "Suppress from paid targeting; they distort cost per acquisition.",
    ),
)

SEGMENTS_BY_KEY: dict[str, RfmSegment] = {s.key: s for s in RFM_SEGMENTS}


def _classify(row: pd.Series) -> str:
    """Assign one customer to a named segment from their R/F/M scores.

    A readable rule ladder rather than a 125-cell lookup table: a PM has to be
    able to check the definition against the chart without a decoder ring.
    """
    r, f, m = int(row["r_score"]), int(row["f_score"]), int(row["m_score"])
    fm = (f + m) / 2

    if r >= 4 and fm >= 4.5:
        return "champions"
    if r >= 3 and fm >= 3.5:
        return "loyal"
    if r >= 4 and f <= 1:
        return "new_customers"
    if r >= 3 and fm >= 2:
        return "potential_loyalist"
    if r <= 2 and m >= 4.5:
        return "cant_lose"
    if r <= 2 and fm >= 2.5:
        return "at_risk"
    if r <= 2 and fm >= 1.5:
        return "hibernating"
    return "lost"


def rfm_segments(data_source: str = "REAL_DATASET") -> pd.DataFrame:
    """Customers with their RFM scores and assigned segment."""
    statement = text(
        """
        SELECT user_id, recency_days, frequency, monetary, avg_order_value,
               clv_historical, r_score, f_score, m_score, country,
               first_order_on, last_order_on, tenure_days
        FROM mart_customers
        WHERE data_source::text = :data_source
        """
    )
    with get_engine().connect() as connection:
        frame = pd.read_sql_query(statement, connection, params={"data_source": data_source})

    if frame.empty:
        return frame

    frame["segment"] = frame.apply(_classify, axis=1)
    frame["segment_label"] = frame["segment"].map(lambda key: SEGMENTS_BY_KEY[key].label)
    return frame


def segment_kpis(data_source: str = "REAL_DATASET") -> pd.DataFrame:
    """Size and value of each RFM segment, ordered by revenue at stake."""
    customers = rfm_segments(data_source)
    if customers.empty:
        return customers

    grouped = (
        customers.groupby(["segment", "segment_label"])
        .agg(
            customers=("user_id", "count"),
            revenue=("monetary", "sum"),
            avg_clv=("clv_historical", "mean"),
            avg_orders=("frequency", "mean"),
            avg_order_value=("avg_order_value", "mean"),
            avg_recency_days=("recency_days", "mean"),
        )
        .reset_index()
    )
    total_revenue = grouped["revenue"].sum()
    grouped["revenue_share"] = grouped["revenue"] / total_revenue if total_revenue else 0.0
    grouped["customer_share"] = grouped["customers"] / grouped["customers"].sum()
    grouped["description"] = grouped["segment"].map(lambda k: SEGMENTS_BY_KEY[k].description)
    grouped["action"] = grouped["segment"].map(lambda k: SEGMENTS_BY_KEY[k].action)
    return grouped.sort_values("revenue", ascending=False).reset_index(drop=True)


#: Features the behavioural clustering runs on, in a fixed order.
CLUSTER_FEATURES: tuple[str, ...] = (
    "recency_days",
    "frequency",
    "monetary",
    "avg_order_value",
    "tenure_days",
)


def behavioural_clusters(
    data_source: str = "REAL_DATASET", k: int = 4, random_state: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """K-means clusters over customer behaviour.

    Returns the per-customer assignment and a per-cluster profile carrying a
    plain-English description derived from how the cluster actually sits
    against the population, rather than a hand-written label that could drift
    away from the data.
    """
    customers = rfm_segments(data_source)
    if customers.empty or len(customers) < k:
        return customers, pd.DataFrame()

    features = customers[list(CLUSTER_FEATURES)].astype(float)
    # Monetary and tenure are on wildly different scales; without standardising,
    # k-means would effectively cluster on spend alone.
    scaled = StandardScaler().fit_transform(features)
    model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    customers = customers.copy()
    customers["cluster"] = model.fit_predict(scaled)

    profile = (
        customers.groupby("cluster")[list(CLUSTER_FEATURES)]
        .mean()
        .join(customers.groupby("cluster").size().rename("customers"))
        .reset_index()
    )
    population = features.mean()

    def describe(row: pd.Series) -> str:
        bits: list[str] = []
        bits.append(
            "recent buyers" if row["recency_days"] < population["recency_days"] else "long lapsed"
        )
        bits.append("order often" if row["frequency"] > population["frequency"] else "order rarely")
        if row["avg_order_value"] > population["avg_order_value"] * 1.25:
            bits.append("with large baskets")
        elif row["avg_order_value"] < population["avg_order_value"] * 0.75:
            bits.append("with small baskets")
        else:
            bits.append("with typical baskets")
        return ", ".join(bits).capitalize() + "."

    profile["description"] = profile.apply(describe, axis=1)
    profile["revenue_share"] = (profile["monetary"] * profile["customers"]) / (
        profile["monetary"] * profile["customers"]
    ).sum()
    return customers, profile.sort_values("customers", ascending=False).reset_index(drop=True)
