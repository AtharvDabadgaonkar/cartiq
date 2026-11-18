"""Customer segmentation: RFM segments and behavioural clusters."""

from __future__ import annotations

import altair as alt
import streamlit as st

from cartiq_console.controls import SOURCE_BADGE, empty_state, snapshot_notice
from cartiq_console.source import (
    available_sources,
    behavioural_clusters,
    is_snapshot,
    rfm_segments,
    segment_kpis,
)
from cartiq_console.theme import CHART_COLORS, data_source_badge

st.title("Segments")

sources = [s for s in available_sources() if s != "LIVE_DEMO"] or available_sources()
default_index = sources.index("REAL_DATASET") if "REAL_DATASET" in sources else 0
data_source = st.sidebar.selectbox(
    "Data source",
    sources,
    index=default_index,
    format_func=lambda s: s.replace("_", " ").title(),
    help="Segmentation needs repeat purchase behaviour, which the real dataset has.",
)

data_source_badge(SOURCE_BADGE.get(data_source, "none"))
if is_snapshot():
    snapshot_notice()

if data_source == "REAL_DATASET":
    st.caption(
        "Computed from real purchase behaviour. Only attributed customers are scored: the "
        "import keeps unattributed lines so revenue reconciles, but they cannot be assigned "
        "to a person, so they are excluded here rather than silently bucketed."
    )

summary = segment_kpis(data_source)
if summary.empty:
    empty_state("No attributed customers for this source.")
    st.stop()

customers = rfm_segments(data_source)

a, b, c = st.columns(3)
a.metric("Customers scored", f"{int(summary['customers'].sum()):,}")
b.metric("Revenue covered", f"£{summary['revenue'].sum():,.0f}")
c.metric("Mean historical CLV", f"£{customers['clv_historical'].mean():,.2f}")

# --- RFM -------------------------------------------------------------------
st.subheader("RFM segments")
st.caption(
    "Recency, frequency and monetary value, each scored into quintiles within this source, "
    "then combined into named segments. Recency is measured against the last date in the "
    "data, not today — the dataset ends in 2011, so a wall-clock recency would make every "
    "customer look lapsed."
)

left, right = st.columns([3, 2])
with left:
    chart = (
        alt.Chart(summary)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            y=alt.Y("segment_label:N", sort="-x", title=None),
            x=alt.X("revenue:Q", title="Revenue (£)"),
            color=alt.Color(
                "segment_label:N",
                legend=None,
                scale=alt.Scale(range=list(CHART_COLORS)),
            ),
            tooltip=[
                alt.Tooltip("segment_label:N", title="Segment"),
                alt.Tooltip("customers:Q", title="Customers", format=","),
                alt.Tooltip("revenue:Q", title="Revenue", format=",.0f"),
                alt.Tooltip("revenue_share:Q", title="Share of revenue", format=".1%"),
                alt.Tooltip("avg_clv:Q", title="Mean CLV", format=",.0f"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)

with right:
    scatter = (
        alt.Chart(customers.sample(min(len(customers), 2000), random_state=42))
        .mark_circle(opacity=0.5, size=28)
        .encode(
            x=alt.X("recency_days:Q", title="Days since last order"),
            y=alt.Y(
                "monetary:Q",
                scale=alt.Scale(type="log"),
                title="Lifetime spend (£, log)",
            ),
            color=alt.Color(
                "segment_label:N",
                title="Segment",
                scale=alt.Scale(range=list(CHART_COLORS)),
            ),
            tooltip=["segment_label", "recency_days", "frequency", "monetary"],
        )
        .properties(height=300)
    )
    st.altair_chart(scatter, use_container_width=True)

st.dataframe(
    summary[
        [
            "segment_label",
            "customers",
            "customer_share",
            "revenue",
            "revenue_share",
            "avg_clv",
            "avg_orders",
            "avg_order_value",
            "avg_recency_days",
            "description",
            "action",
        ]
    ].rename(
        columns={
            "segment_label": "Segment",
            "customers": "Customers",
            "customer_share": "Share of customers",
            "revenue": "Revenue",
            "revenue_share": "Share of revenue",
            "avg_clv": "Mean CLV",
            "avg_orders": "Mean orders",
            "avg_order_value": "Mean order value",
            "avg_recency_days": "Mean days since order",
            "description": "What it means",
            "action": "What to do",
        }
    ),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Share of customers": st.column_config.NumberColumn(format="%.1f%%"),
        "Share of revenue": st.column_config.NumberColumn(format="%.1f%%"),
        "Revenue": st.column_config.NumberColumn(format="£%.0f"),
        "Mean CLV": st.column_config.NumberColumn(format="£%.0f"),
        "Mean order value": st.column_config.NumberColumn(format="£%.0f"),
        "Mean orders": st.column_config.NumberColumn(format="%.1f"),
        "Mean days since order": st.column_config.NumberColumn(format="%.0f"),
    },
)

top = summary.iloc[0]
st.markdown(
    f"**{top['segment_label']}** hold the most revenue: {int(top['customers']):,} customers "
    f"({top['customer_share']:.0%} of the base) carrying £{top['revenue']:,.0f} "
    f"({top['revenue_share']:.0%} of revenue). {top['action']}"
)

# --- Clusters --------------------------------------------------------------
st.divider()
st.subheader("Behavioural clusters")
st.caption(
    "K-means over recency, frequency, monetary value, average order value and tenure, "
    "standardised first — without that, the spend column alone would decide the clusters. "
    "Descriptions are derived from where each cluster sits against the population, so they "
    "cannot drift away from the data."
)

k = st.slider("Clusters", min_value=2, max_value=6, value=4)
assigned, profile = behavioural_clusters(data_source, k=k)

if profile.empty:
    empty_state("Not enough customers to cluster.")
else:
    profile_display = profile.copy()
    profile_display["cluster"] = profile_display["cluster"].map(
        lambda i: f"Cluster {i + 1}"
    )
    st.dataframe(
        profile_display[
            [
                "cluster",
                "customers",
                "description",
                "recency_days",
                "frequency",
                "monetary",
                "avg_order_value",
                "tenure_days",
            ]
        ].rename(
            columns={
                "cluster": "Cluster",
                "customers": "Customers",
                "description": "In plain English",
                "recency_days": "Mean days since order",
                "frequency": "Mean orders",
                "monetary": "Mean lifetime spend",
                "avg_order_value": "Mean order value",
                "tenure_days": "Mean tenure (days)",
            }
        ),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Mean lifetime spend": st.column_config.NumberColumn(format="£%.0f"),
            "Mean order value": st.column_config.NumberColumn(format="£%.0f"),
            "Mean days since order": st.column_config.NumberColumn(format="%.0f"),
            "Mean orders": st.column_config.NumberColumn(format="%.1f"),
            "Mean tenure (days)": st.column_config.NumberColumn(format="%.0f"),
        },
    )

    cluster_chart = (
        alt.Chart(assigned.sample(min(len(assigned), 2000), random_state=42))
        .mark_circle(opacity=0.55, size=30)
        .encode(
            x=alt.X("frequency:Q", title="Orders"),
            y=alt.Y(
                "monetary:Q",
                scale=alt.Scale(type="log"),
                title="Lifetime spend (£, log)",
            ),
            color=alt.Color(
                "cluster:N", title="Cluster", scale=alt.Scale(range=list(CHART_COLORS))
            ),
            tooltip=["cluster", "frequency", "monetary", "recency_days"],
        )
        .properties(height=320)
    )
    st.altair_chart(cluster_chart, use_container_width=True)

st.caption("Segment definitions are documented in docs/METRICS_DICTIONARY.md.")
