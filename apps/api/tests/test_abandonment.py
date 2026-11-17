"""Abandonment model and nudge engine."""

import pytest
from sqlalchemy import text

from cartiq_api.db import get_engine, ping
from cartiq_api.ml.abandonment import (
    BOOLEAN_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    NotEnoughDataError,
    export_logistic_model,
    load_cart_sessions,
    train_abandonment_model,
)
from cartiq_api.nudges import (
    FREE_SHIPPING_NUDGE_GAP,
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
    NUDGE_FLAGS,
    CartContext,
    choose_nudge,
    describe_rules,
)

ALL_FLAGS = frozenset(NUDGE_FLAGS)


def _ready() -> bool:
    if not ping():
        return False
    try:
        with get_engine().connect() as connection:
            count = connection.execute(
                text("SELECT COUNT(*) FROM mart_cart_sessions WHERE data_source='SIMULATED'")
            ).scalar()
        return bool(count and count >= 2000)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Nudge rules (pure, no database)
# ---------------------------------------------------------------------------


def context(**overrides) -> CartContext:
    base = {
        "cart_value": 32.5,
        "items": 3,
        "risk_score": 0.9,
        "pays_shipping": True,
        "gap_to_free_shipping": 7.5,
    }
    base.update(overrides)
    return CartContext(**base)


def test_low_risk_carts_are_left_alone():
    assert choose_nudge(context(risk_score=0.4), ALL_FLAGS) is None
    assert choose_nudge(context(risk_score=MEDIUM_RISK_THRESHOLD - 0.01), ALL_FLAGS) is None


def test_free_shipping_nudge_wins_when_the_threshold_is_in_reach():
    nudge = choose_nudge(context(), ALL_FLAGS)
    assert nudge is not None
    assert nudge.key == "free_shipping_threshold"
    assert "7.50" in nudge.headline


def test_free_shipping_nudge_is_silent_when_the_gap_is_hopeless():
    # Telling someone they are £38 away is not help, it is noise.
    nudge = choose_nudge(
        context(cart_value=2.0, gap_to_free_shipping=FREE_SHIPPING_NUDGE_GAP + 23), ALL_FLAGS
    )
    assert nudge is None or nudge.key != "free_shipping_threshold"


def test_free_shipping_nudge_is_silent_when_shipping_is_already_free():
    nudge = choose_nudge(
        context(cart_value=60, pays_shipping=False, gap_to_free_shipping=0), ALL_FLAGS
    )
    assert nudge is None or nudge.key != "free_shipping_threshold"


def test_high_risk_falls_through_to_the_saved_cart_message():
    nudge = choose_nudge(
        context(risk_score=HIGH_RISK_THRESHOLD, pays_shipping=False, gap_to_free_shipping=0),
        ALL_FLAGS,
    )
    assert nudge is not None
    assert nudge.key == "saved_cart_reminder"


def test_only_one_nudge_is_ever_returned():
    # Every rule could match here; exactly one must come back.
    nudge = choose_nudge(context(risk_score=0.99), ALL_FLAGS)
    assert nudge is not None
    assert isinstance(nudge.key, str)


def test_each_nudge_can_be_switched_off_independently():
    without_shipping = choose_nudge(context(), ALL_FLAGS - {"nudge_free_shipping"})
    assert without_shipping is not None
    assert without_shipping.key != "free_shipping_threshold"

    assert choose_nudge(context(), frozenset()) is None


def test_every_nudge_declares_its_own_flag():
    for flag in NUDGE_FLAGS:
        nudge = choose_nudge(context(risk_score=0.99), frozenset({flag}))
        if nudge is not None:
            assert nudge.flag == flag


def test_every_nudge_explains_why_it_fired():
    nudge = choose_nudge(context(), ALL_FLAGS)
    assert nudge is not None
    assert "risk" in nudge.rationale


def test_rule_table_covers_every_flag():
    documented = {row["flag"] for row in describe_rules()}
    assert set(NUDGE_FLAGS) <= documented


def test_thresholds_match_the_typescript_rules():
    """The storefront decides in TypeScript; both must agree on when to interrupt."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[3] / "packages" / "shared" / "src" / "nudges.ts"
    ).read_text()
    assert f"MEDIUM_RISK_THRESHOLD = {MEDIUM_RISK_THRESHOLD}" in source
    assert f"HIGH_RISK_THRESHOLD = {HIGH_RISK_THRESHOLD}" in source
    assert f"FREE_SHIPPING_NUDGE_GAP = {FREE_SHIPPING_NUDGE_GAP}" in source
    for flag in NUDGE_FLAGS:
        assert f"'{flag}'" in source


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

pytestmark_model = pytest.mark.skipif(
    not _ready(), reason="not enough carting sessions loaded (run make simulate)"
)


@pytestmark_model
def test_training_data_excludes_post_cart_features():
    """The leakage guard: nothing the shopper does after carting may be a feature."""
    frame = load_cart_sessions("SIMULATED")
    forbidden = {
        "reached_checkout",
        "reached_shipping",
        "reached_payment",
        "reached_purchase",
        "converted",
        "revenue",
        "max_step_depth",
    }
    assert forbidden.isdisjoint(frame.columns)


@pytestmark_model
def test_feature_lists_are_all_present_in_the_training_data():
    frame = load_cart_sessions("SIMULATED")
    for feature in CATEGORICAL_FEATURES + NUMERIC_FEATURES + BOOLEAN_FEATURES:
        assert feature in frame.columns, feature


@pytestmark_model
def test_seconds_to_cart_is_never_negative():
    # Negative values meant two simulation runs had merged into one session.
    frame = load_cart_sessions("SIMULATED")
    assert frame["seconds_to_cart"].min() >= 0


@pytestmark_model
def test_model_beats_the_majority_class_baseline():
    result = train_abandonment_model()
    best = result.metrics[result.best_model]
    baseline = result.metrics["majority_class_baseline"]
    assert best["roc_auc"] > 0.55, "no better than a coin flip"
    assert best["average_precision"] > baseline["average_precision"]
    assert best["brier_score"] < baseline["brier_score"]


@pytestmark_model
def test_model_is_calibrated_enough_to_threshold_on():
    """Predicted probabilities must match observed rates, pooled not per bin.

    Asserted two ways, both pooled. A per-bin assertion was tried first and
    abandoned: with ~1.7k carts in the test split, a single bin holds a few
    hundred, so the per-bin gap is dominated by sampling noise and the test
    failed on roughly one split in eight while the model was fine.

    Pooling fixes that without weakening the claim, because what the product
    needs is narrower than per-bin calibration everywhere: the nudge engine
    fires on a threshold, so the number that has to be true is the abandonment
    rate among carts the model puts at or above it.
    """
    result = train_abandonment_model()
    curve = result.calibration
    total = int(curve["count"].sum())
    assert total > 0, "no carts in the reliability curve"

    # 1. Expected calibration error: the count-weighted mean gap across bins.
    error = float((curve["count"] * (curve["predicted"] - curve["observed"]).abs()).sum() / total)
    assert error <= 0.05, f"expected calibration error {error:.3f} exceeds 5pp"

    # 2. Calibration in the region the nudge actually fires in. A model that is
    #    well calibrated on average can still be wrong exactly here, and this is
    #    the only part of the curve the intervention depends on.
    high = curve[curve["bin_lower"] >= MEDIUM_RISK_THRESHOLD]
    assert not high.empty, "no carts scored at or above the nudge threshold"
    n = int(high["count"].sum())
    predicted = float((high["predicted"] * high["count"]).sum() / n)
    observed = float((high["observed"] * high["count"]).sum() / n)
    assert abs(predicted - observed) <= 0.05, (
        f"above the {MEDIUM_RISK_THRESHOLD:.2f} nudge threshold (n={n:,}): "
        f"predicted {predicted:.3f} vs observed {observed:.3f}"
    )


@pytestmark_model
def test_selection_never_prefers_a_worse_calibrated_model():
    """The shipped model must not lose to a rejected one on Brier score.

    Selecting on average precision used to allow exactly that: on some splits
    it preferred the boosted model by ~0.008 AP while that model was worse on
    AUC and 1pp worse on Brier, which put a 7pp kink in the reliability curve
    right where the nudge fires. Selection is on Brier now; this pins it.
    """
    result = train_abandonment_model()
    best = result.metrics[result.best_model]
    for name, metrics in result.metrics.items():
        if name == result.best_model:
            continue
        assert best["brier_score"] <= metrics["brier_score"], (
            f"{result.best_model} was selected but {name} is better calibrated "
            f"({best['brier_score']:.4f} vs {metrics['brier_score']:.4f})"
        )


@pytestmark_model
def test_training_is_reproducible():
    first = train_abandonment_model()
    second = train_abandonment_model()
    assert first.metrics == second.metrics
    assert first.best_model == second.best_model


@pytestmark_model
def test_export_round_trips_the_shape_the_storefront_needs():
    result = train_abandonment_model()
    exported = export_logistic_model(result)
    assert len(exported["coefficients"]) == len(exported["feature_names"])
    assert len(exported["numeric"]["mean"]) == len(exported["numeric"]["features"])
    assert len(exported["numeric"]["scale"]) == len(exported["numeric"]["features"])
    assert exported["categorical"]["drop_first"] is True
    # Dropping the first level means one fewer column per categorical feature.
    expected = sum(
        len(values) - 1 for values in exported["categorical"]["categories"].values()
    ) + len(exported["numeric"]["features"])
    assert len(exported["coefficients"]) == expected


def test_training_refuses_rather_than_pretending_on_thin_data():
    with pytest.raises(NotEnoughDataError, match="not enough"):
        train_abandonment_model(data_source="LIVE_DEMO")
