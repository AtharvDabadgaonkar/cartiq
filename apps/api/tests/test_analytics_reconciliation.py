"""Every console figure must reconcile against direct SQL.

This is the Module 1 acceptance criterion. The analytics layer builds its
numbers through views and pandas; these tests recompute the same numbers with
independent SQL straight off `events` and assert they agree. A disagreement
means a chart is lying, which is the one failure this project cannot tolerate.
"""

import pandas as pd
import pytest
from sqlalchemy import text

from cartiq_api.analytics import Filters, friction_ranking, funnel, funnel_by_dimension, kpis
from cartiq_api.analytics.kpis import KPI_DEFINITIONS
from cartiq_api.db import get_engine, ping


def _models_ready() -> bool:
    if not ping():
        return False
    try:
        with get_engine().connect() as connection:
            rows = connection.execute(text("SELECT COUNT(*) FROM mart_funnel")).scalar()
        # An empty table is not a passing test, it is a missing fixture.
        return bool(rows)
    except Exception:  # a missing view is a skip, not a failure
        return False


pytestmark = pytest.mark.skipif(
    not _models_ready(), reason="database unreachable or models not built"
)

SIMULATED = Filters(data_source="SIMULATED")


def scalar(sql: str, **params) -> float:
    with get_engine().connect() as connection:
        return float(connection.execute(text(sql), params).scalar() or 0)


# ---------------------------------------------------------------------------
# Funnel
# ---------------------------------------------------------------------------


def test_funnel_visit_count_matches_distinct_sessions():
    steps = funnel(SIMULATED)
    direct = scalar(
        "SELECT COUNT(DISTINCT session_id) FROM events "
        "WHERE source = 'SIMULATED' AND event_type = 'session_start'"
    )
    assert int(steps.loc[steps["step_key"] == "visit", "sessions"].iloc[0]) == int(direct)


def test_funnel_purchase_count_matches_distinct_purchasing_sessions():
    steps = funnel(SIMULATED)
    direct = scalar(
        "SELECT COUNT(DISTINCT session_id) FROM events "
        "WHERE source = 'SIMULATED' AND event_type = 'purchase'"
    )
    assert int(steps.loc[steps["step_key"] == "purchase", "sessions"].iloc[0]) == int(direct)


def test_every_funnel_step_matches_direct_sql():
    # Mirrors FUNNEL_STEPS, written out independently so a bug in the view's
    # step mapping cannot hide behind the same mapping in the test.
    direct_sql = {
        "visit": "event_type = 'session_start'",
        "browse": "event_type IN ('page_view', 'search')",
        "product_view": "event_type = 'product_view'",
        "add_to_cart": "event_type = 'add_to_cart'",
        "checkout": "event_type = 'checkout_start'",
        "shipping": "event_type = 'shipping_step'",
        "payment": "event_type = 'payment_step'",
        "purchase": "event_type = 'purchase'",
    }
    steps = funnel(SIMULATED).set_index("step_key")
    for step_key, predicate in direct_sql.items():
        expected = scalar(
            f"SELECT COUNT(DISTINCT session_id) FROM events "
            f"WHERE source = 'SIMULATED' AND {predicate}"
        )
        assert int(steps.loc[step_key, "sessions"]) == int(expected), step_key


def test_funnel_is_monotonically_non_increasing():
    steps = funnel(SIMULATED)
    sessions = steps["sessions"].tolist()
    assert sessions == sorted(sessions, reverse=True), "a later step cannot gain sessions"


def test_funnel_rates_are_internally_consistent():
    steps = funnel(SIMULATED)
    entered = steps["sessions"].iloc[0]
    for _, row in steps.iterrows():
        assert row["overall_rate"] == pytest.approx(row["sessions"] / entered)
    for index in range(1, len(steps)):
        previous = steps["sessions"].iloc[index - 1]
        row = steps.iloc[index]
        assert row["step_rate"] == pytest.approx(row["sessions"] / previous)
        assert int(row["dropped"]) == int(previous - row["sessions"])


def test_funnel_always_returns_every_step_even_when_empty():
    empty = funnel(Filters(data_source="SIMULATED", devices=("does-not-exist",)))
    assert len(empty) == 8
    assert empty["sessions"].sum() == 0


def test_funnel_split_sums_back_to_the_whole():
    whole = funnel(SIMULATED)
    split = funnel_by_dimension("device", SIMULATED)
    for step_key in whole["step_key"]:
        expected = int(whole.loc[whole["step_key"] == step_key, "sessions"].iloc[0])
        actual = int(split.loc[split["step_key"] == step_key, "sessions"].sum())
        assert actual == expected, step_key


def test_funnel_rejects_an_arbitrary_split_column():
    with pytest.raises(ValueError, match="dimension must be one of"):
        funnel_by_dimension("session_id; DROP TABLE events", SIMULATED)


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------


def test_conversion_rate_matches_direct_sql():
    measures = kpis(SIMULATED)
    converted = scalar(
        "SELECT COUNT(DISTINCT session_id) FROM events "
        "WHERE source='SIMULATED' AND event_type='purchase'"
    )
    sessions = scalar("SELECT COUNT(DISTINCT session_id) FROM events WHERE source='SIMULATED'")
    assert measures["conversion_rate"]["value"] == pytest.approx(converted / sessions)


def test_revenue_matches_direct_sql():
    measures = kpis(SIMULATED)
    # Simulated purchases are order-grained: price IS the order total.
    direct = scalar(
        "SELECT COALESCE(SUM(price), 0) FROM events "
        "WHERE source='SIMULATED' AND event_type='purchase'"
    )
    assert measures["revenue"]["value"] == pytest.approx(direct, rel=1e-6)


def test_real_revenue_uses_the_line_grained_rule():
    # A transactional import is line-grained: revenue is price * quantity.
    direct = scalar(
        "SELECT COALESCE(SUM(price * quantity), 0) FROM events "
        "WHERE source='REAL_DATASET' AND event_type='purchase'"
    )
    modelled = scalar(
        "SELECT COALESCE(SUM(revenue), 0) FROM int_orders WHERE data_source='REAL_DATASET'"
    )
    assert modelled == pytest.approx(direct, rel=1e-6)


def test_cart_abandonment_matches_direct_sql():
    measures = kpis(SIMULATED)
    direct = scalar(
        """
        WITH s AS (
            SELECT session_id,
                   BOOL_OR(event_type = 'add_to_cart') AS carted,
                   BOOL_OR(event_type = 'purchase')    AS bought
            FROM events WHERE source = 'SIMULATED' GROUP BY session_id
        )
        SELECT COUNT(*) FILTER (WHERE carted AND NOT bought)::float8
             / NULLIF(COUNT(*) FILTER (WHERE carted), 0)
        FROM s
        """
    )
    assert measures["cart_abandonment_rate"]["value"] == pytest.approx(direct)


def test_search_to_purchase_matches_direct_sql():
    measures = kpis(SIMULATED)
    direct = scalar(
        """
        WITH s AS (
            SELECT session_id,
                   BOOL_OR(event_type = 'search')   AS searched,
                   BOOL_OR(event_type = 'purchase') AS bought
            FROM events WHERE source = 'SIMULATED' GROUP BY session_id
        )
        SELECT COUNT(*) FILTER (WHERE searched AND bought)::float8
             / NULLIF(COUNT(*) FILTER (WHERE searched), 0)
        FROM s
        """
    )
    expected = measures["search_to_purchase_rate"]["value"]
    if expected is None:
        assert direct == 0
    else:
        assert expected == pytest.approx(direct)


def test_session_denominated_kpis_are_refused_for_a_transactional_source():
    """The honesty rule, enforced: no 100% conversion rate from an order import."""
    measures = kpis(Filters(data_source="REAL_DATASET"))
    for definition in KPI_DEFINITIONS:
        entry = measures[definition.key]
        if definition.requires_sessions:
            assert entry["available"] is False, definition.key
            assert entry["value"] is None, definition.key
            assert "converted by construction" in entry["reason"]
        else:
            # Order-grained metrics remain perfectly meaningful there.
            assert entry["value"] is not None, definition.key


def test_filters_narrow_rather_than_widen():
    everything = kpis(SIMULATED)["_context"]["sessions"]
    mobile = kpis(Filters(data_source="SIMULATED", devices=("mobile",)))["_context"]["sessions"]
    assert 0 < mobile < everything


def test_filter_values_are_bound_not_interpolated():
    # A hostile filter value must come back as an empty slice, not an error.
    hostile = Filters(data_source="SIMULATED", devices=("'; DROP TABLE events; --",))
    assert kpis(hostile)["_context"]["sessions"] == 0
    assert scalar("SELECT COUNT(*) FROM events") > 0


# ---------------------------------------------------------------------------
# Friction
# ---------------------------------------------------------------------------


def test_friction_shares_sum_to_one():
    ranking = friction_ranking(SIMULATED)
    assert not ranking.empty
    assert ranking["share_of_loss"].sum() == pytest.approx(1.0)


def test_friction_is_sorted_by_revenue_at_risk():
    ranking = friction_ranking(SIMULATED)
    assert ranking["revenue_at_risk"].tolist() == sorted(
        ranking["revenue_at_risk"].tolist(), reverse=True
    )


def test_friction_dropped_counts_match_the_funnel():
    steps = funnel(SIMULATED).set_index("step_key")
    for _, row in friction_ranking(SIMULATED).iterrows():
        assert int(row["dropped"]) == int(steps.loc[row["step_key"], "dropped"])


def test_friction_is_empty_for_an_empty_slice():
    empty = friction_ranking(Filters(data_source="SIMULATED", devices=("does-not-exist",)))
    assert empty.empty


# ---------------------------------------------------------------------------
# Performance (Module 1 acceptance: dashboards load in under 2s on seed data)
# ---------------------------------------------------------------------------


def test_funnel_and_kpis_are_fast_enough_for_a_dashboard():
    import time

    start = time.perf_counter()
    funnel(SIMULATED)
    kpis(SIMULATED)
    friction_ranking(SIMULATED)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"diagnosis queries took {elapsed:.2f}s; budget is 2s"


def test_results_are_dataframes_with_stable_columns():
    steps = funnel(SIMULATED)
    assert isinstance(steps, pd.DataFrame)
    assert list(steps.columns[:3]) == ["step_key", "step_label", "step_index"]
