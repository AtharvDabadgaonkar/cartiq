"""RFM segmentation and behavioural clusters."""

import pandas as pd
import pytest
from sqlalchemy import text

from cartiq_api.analytics import behavioural_clusters, rfm_segments, segment_kpis
from cartiq_api.analytics.segmentation import RFM_SEGMENTS, _classify
from cartiq_api.db import get_engine, ping


def _models_ready() -> bool:
    if not ping():
        return False
    try:
        with get_engine().connect() as connection:
            rows = connection.execute(text("SELECT COUNT(*) FROM mart_customers")).scalar()
        # An empty table is not a passing test, it is a missing fixture.
        return bool(rows)
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _models_ready(), reason="database unreachable or models not built"
)


# --- classification rules (pure, no database) ------------------------------


def score(r: int, f: int, m: int) -> str:
    return _classify(pd.Series({"r_score": r, "f_score": f, "m_score": m}))


def test_best_scores_are_champions():
    assert score(5, 5, 5) == "champions"


def test_worst_scores_are_lost():
    assert score(1, 1, 1) == "lost"


def test_a_recent_first_time_buyer_is_a_new_customer():
    assert score(5, 1, 1) == "new_customers"


def test_a_lapsed_big_spender_is_cant_lose():
    # The costliest group to misfile: high spend, gone quiet.
    assert score(1, 3, 5) == "cant_lose"


def test_a_lapsed_frequent_buyer_is_at_risk():
    assert score(2, 4, 3) == "at_risk"


def test_every_score_combination_lands_in_a_known_segment():
    keys = {s.key for s in RFM_SEGMENTS}
    for r in range(1, 6):
        for f in range(1, 6):
            for m in range(1, 6):
                assert score(r, f, m) in keys, (r, f, m)


def test_every_segment_carries_a_description_and_an_action():
    for segment in RFM_SEGMENTS:
        assert segment.description.strip()
        assert segment.action.strip()


# --- against the loaded data ----------------------------------------------


def test_recency_is_measured_against_the_data_not_the_wall_clock():
    customers = rfm_segments("REAL_DATASET")
    assert not customers.empty
    # The dataset ends in 2011; a wall-clock recency would be ~5000+ days.
    assert customers["recency_days"].max() < 1000


def test_scores_span_the_full_quintile_range():
    customers = rfm_segments("REAL_DATASET")
    for column in ("r_score", "f_score", "m_score"):
        assert customers[column].min() == 1
        assert customers[column].max() == 5


def test_segment_sizes_sum_to_the_customer_base():
    customers = rfm_segments("REAL_DATASET")
    summary = segment_kpis("REAL_DATASET")
    assert summary["customers"].sum() == len(customers)
    assert summary["revenue_share"].sum() == pytest.approx(1.0)
    assert summary["customer_share"].sum() == pytest.approx(1.0)


def test_segment_revenue_matches_the_customer_mart():
    summary = segment_kpis("REAL_DATASET")
    with get_engine().connect() as connection:
        direct = float(
            connection.execute(
                text("SELECT SUM(monetary) FROM mart_customers WHERE data_source='REAL_DATASET'")
            ).scalar()
        )
    assert summary["revenue"].sum() == pytest.approx(direct, rel=1e-6)


def test_only_attributed_customers_are_scored():
    customers = rfm_segments("REAL_DATASET")
    assert customers["user_id"].notna().all()
    assert customers["user_id"].is_unique


def test_segment_summary_is_ordered_by_revenue():
    summary = segment_kpis("REAL_DATASET")
    assert summary["revenue"].tolist() == sorted(summary["revenue"].tolist(), reverse=True)


def test_unknown_source_returns_empty_rather_than_raising():
    assert rfm_segments("NOT_A_SOURCE").empty
    assert segment_kpis("NOT_A_SOURCE").empty


# --- clustering ------------------------------------------------------------


def test_clustering_is_reproducible():
    first, profile_a = behavioural_clusters("REAL_DATASET", k=4)
    second, profile_b = behavioural_clusters("REAL_DATASET", k=4)
    assert first["cluster"].tolist() == second["cluster"].tolist()
    assert profile_a["description"].tolist() == profile_b["description"].tolist()


def test_clustering_assigns_every_customer_exactly_once():
    assigned, profile = behavioural_clusters("REAL_DATASET", k=4)
    assert len(assigned) == len(rfm_segments("REAL_DATASET"))
    assert int(profile["customers"].sum()) == len(assigned)
    assert assigned["cluster"].nunique() == 4


def test_cluster_descriptions_are_plain_english():
    _, profile = behavioural_clusters("REAL_DATASET", k=4)
    for description in profile["description"]:
        assert description.endswith(".")
        assert "cluster" not in description.lower()
        # Must say something about recency, frequency and basket size.
        assert any(word in description.lower() for word in ("recent", "lapsed"))
        assert "order" in description.lower()
        assert "basket" in description.lower()


def test_clustering_handles_too_few_customers():
    assigned, profile = behavioural_clusters("LIVE_DEMO", k=50)
    assert profile.empty
    assert "cluster" not in assigned.columns
