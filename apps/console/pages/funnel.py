"""Journey funnel, KPIs and the revenue-weighted friction ranking."""

from __future__ import annotations

import altair as alt
import streamlit as st

from cartiq_api.analytics import friction_ranking, funnel, funnel_by_dimension, kpis
from cartiq_api.analytics.friction import friction_by_segment
from cartiq_api.analytics.kpis import KPI_DEFINITIONS
from cartiq_console.controls import (
    SOURCE_BADGE,
    empty_state,
    filter_sidebar,
    format_value,
)
from cartiq_console.theme import AMBER, CHART_COLORS, CLAY, data_source_badge

st.title("Funnel")

filters = filter_sidebar(funnel_only=True, key="funnel")
data_source_badge(SOURCE_BADGE.get(filters.data_source, "none"))
st.caption(filters.describe())

if filters.data_source == "SIMULATED":
    st.caption(
        "The real dataset records purchases, not browsing, so it cannot express a journey "
        "funnel: every session in it converted by construction. These steps are measured on "
        "**simulated** sessions, with the behavioural parameters in docs/SIMULATION.md."
    )

steps = funnel(filters)
entered = int(steps["sessions"].iloc[0]) if not steps.empty else 0

if entered == 0:
    empty_state("No sessions match this slice. Widen the filters in the sidebar.")
    st.stop()

# --- KPI tiles -------------------------------------------------------------
measures = kpis(filters)
tiles = [
    "conversion_rate",
    "aov",
    "revenue_per_visitor",
    "cart_abandonment_rate",
    "search_to_purchase_rate",
    "clv_historical",
]
definitions = {d.key: d for d in KPI_DEFINITIONS}

for row_start in range(0, len(tiles), 3):
    columns = st.columns(3)
    for column, key in zip(columns, tiles[row_start : row_start + 3], strict=False):
        entry = measures[key]
        with column:
            st.metric(
                entry["label"],
                format_value(entry["value"], entry["unit"])
                if entry["available"]
                else "—",
                help=entry["definition"]
                + (
                    ""
                    if entry["available"]
                    else f"\n\nNot available: {entry.get('reason', '')}"
                ),
            )
            if not entry["available"]:
                # Say WHY: "no sessions used search" and "this source cannot
                # express a rate at all" are very different statements.
                reason = entry.get("reason", "")
                label = (
                    "not measurable from this source"
                    if "by construction" in reason
                    else "no data in this slice"
                )
                st.caption(f":gray-badge[{label}]")
            elif definitions[key].lower_is_better:
                st.caption(":gray-badge[lower is better]")

st.divider()

# --- Funnel ----------------------------------------------------------------
st.subheader("Where sessions are lost")

chart_frame = steps.copy()
chart_frame["label"] = chart_frame["step_label"]
chart_frame["share"] = chart_frame["overall_rate"]

bars = (
    alt.Chart(chart_frame)
    .mark_bar(cornerRadiusEnd=3, color=AMBER)
    .encode(
        y=alt.Y("label:N", sort=list(chart_frame["label"]), title=None),
        x=alt.X("sessions:Q", title="Sessions"),
        tooltip=[
            alt.Tooltip("label:N", title="Step"),
            alt.Tooltip("sessions:Q", title="Sessions", format=","),
            alt.Tooltip("share:Q", title="Share of visits", format=".2%"),
            alt.Tooltip("step_rate:Q", title="Advanced from previous", format=".1%"),
            alt.Tooltip("drop_rate:Q", title="Lost at this step", format=".1%"),
        ],
    )
    .properties(height=320)
)
st.altair_chart(bars, use_container_width=True)

table = steps[
    ["step_label", "sessions", "step_rate", "overall_rate", "dropped", "drop_rate"]
]
st.dataframe(
    table.rename(
        columns={
            "step_label": "Step",
            "sessions": "Sessions",
            "step_rate": "Advanced from previous",
            "overall_rate": "Share of all visits",
            "dropped": "Lost here",
            "drop_rate": "Lost from previous",
        }
    ),
    hide_index=True,
    use_container_width=True,
    column_config={
        "Advanced from previous": st.column_config.NumberColumn(format="%.1f%%"),
        "Share of all visits": st.column_config.NumberColumn(format="%.2f%%"),
        "Lost from previous": st.column_config.NumberColumn(format="%.1f%%"),
        "Sessions": st.column_config.NumberColumn(format="%d"),
        "Lost here": st.column_config.NumberColumn(format="%d"),
    },
)

# --- Friction ranking ------------------------------------------------------
st.divider()
st.subheader("Biggest leaks by revenue")
st.caption(
    "Steps ranked by the revenue the drop there plausibly costs: sessions lost, times the "
    "probability a session reaching that step converts, times revenue per conversion. "
    "It is an upper bound on recoverable revenue, not a forecast — it assumes a recovered "
    "session behaves like one that already got through."
)

ranking = friction_ranking(filters)
if ranking.empty:
    empty_state("No drop-off to rank in this slice.")
else:
    leak = (
        alt.Chart(ranking)
        .mark_bar(cornerRadiusEnd=3, color=CLAY)
        .encode(
            y=alt.Y("step_label:N", sort="-x", title=None),
            x=alt.X("revenue_at_risk:Q", title="Estimated revenue at risk (£)"),
            tooltip=[
                alt.Tooltip("from_label:N", title="Lost between"),
                alt.Tooltip("step_label:N", title="and"),
                alt.Tooltip("dropped:Q", title="Sessions lost", format=","),
                alt.Tooltip("drop_rate:Q", title="Drop rate", format=".1%"),
                alt.Tooltip(
                    "revenue_at_risk:Q", title="Revenue at risk", format=",.0f"
                ),
                alt.Tooltip(
                    "share_of_loss:Q", title="Share of total loss", format=".1%"
                ),
            ],
        )
        .properties(height=240)
    )
    st.altair_chart(leak, use_container_width=True)

    worst = ranking.iloc[0]
    st.markdown(
        f"**Top friction point: {worst['from_label']} → {worst['step_label']}.** "
        f"{int(worst['dropped']):,} sessions lost ({worst['drop_rate']:.1%} of those that got "
        f"there), carrying an estimated £{worst['revenue_at_risk']:,.0f} — "
        f"{worst['share_of_loss']:.0%} of all modelled loss."
    )

    by_segment = friction_by_segment(filters)
    if not by_segment.empty:
        st.caption("A single ranking hides that segments leak in different places:")
        st.dataframe(
            by_segment.rename(
                columns={
                    "segment": "Segment",
                    "worst_step": "Worst step",
                    "drop_rate": "Drop rate",
                    "revenue_at_risk": "Revenue at risk",
                }
            ),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Drop rate": st.column_config.NumberColumn(format="%.1f%%"),
                "Revenue at risk": st.column_config.NumberColumn(format="£%.0f"),
            },
        )

# --- Split by dimension ----------------------------------------------------
st.divider()
st.subheader("Compare a dimension")
dimension = st.selectbox(
    "Split by",
    ["device", "traffic_source", "segment", "is_new_user"],
    format_func=lambda d: d.replace("_", " ").title(),
)

split = funnel_by_dimension(dimension, filters)
if split.empty:
    empty_state("Nothing to split in this slice.")
else:
    lines = (
        alt.Chart(split)
        .mark_line(point=True)
        .encode(
            x=alt.X("step_label:N", sort=list(steps["step_label"]), title=None),
            y=alt.Y(
                "overall_rate:Q", axis=alt.Axis(format="%"), title="Share of visits"
            ),
            color=alt.Color(
                "dimension_value:N",
                title=dimension.replace("_", " ").title(),
                scale=alt.Scale(range=list(CHART_COLORS)),
            ),
            tooltip=[
                alt.Tooltip("dimension_value:N", title="Value"),
                alt.Tooltip("step_label:N", title="Step"),
                alt.Tooltip("sessions:Q", title="Sessions", format=","),
                alt.Tooltip("overall_rate:Q", title="Share of visits", format=".2%"),
            ],
        )
        .properties(height=320)
    )
    st.altair_chart(lines, use_container_width=True)

    final = (
        split[split["step_key"] == "purchase"][
            ["dimension_value", "sessions", "overall_rate"]
        ]
        .rename(
            columns={
                "dimension_value": dimension.replace("_", " ").title(),
                "sessions": "Purchases",
                "overall_rate": "Conversion rate",
            }
        )
        .sort_values("Conversion rate", ascending=False)
    )
    if not final.empty:
        st.dataframe(
            final,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Conversion rate": st.column_config.NumberColumn(format="%.2f%%")
            },
        )

st.caption(
    "Every figure on this page is computed by `cartiq_api.analytics` from the SQL models in "
    "`models/`, and reconciled against direct SQL in the test suite. Definitions are in "
    "docs/METRICS_DICTIONARY.md."
)
