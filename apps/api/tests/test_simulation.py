"""Simulator behaviour.

The important tests here are the ones that back the honesty claims:
determinism, that a configured effect lands on exactly the transition it was
configured for, and that an A/A configuration produces no effect at all.
"""

import math
from dataclasses import replace

import pytest

from cartiq_api.simulation import DEFAULT_PARAMS, simulate
from cartiq_api.simulation.params import (
    TRANSITION_KEYS,
    ExperimentSpec,
    InterventionParams,
    SimulationParams,
)

FUNNEL_ORDER = [
    "visit",
    "browse",
    "product_view",
    "add_to_cart",
    "checkout",
    "shipping",
    "payment",
    "purchase",
]


def small(**overrides) -> SimulationParams:
    """A fast parameter set for tests."""
    return replace(DEFAULT_PARAMS, sessions=4_000, users=2_000, **overrides)


def aa_params(sessions: int = 20_000, seed: int = 42) -> SimulationParams:
    """Identical treatment and control: every configured effect set to 1.0."""
    return replace(
        DEFAULT_PARAMS,
        sessions=sessions,
        seed=seed,
        interventions={
            key: InterventionParams(
                key=intervention.key,
                description=intervention.description,
                effects=dict.fromkeys(intervention.effects, 1.0),
                guardrail_effects=dict.fromkeys(intervention.guardrail_effects, 1.0),
            )
            for key, intervention in DEFAULT_PARAMS.interventions.items()
        },
    )


# --------------------------------------------------------------------------
# Parameter validation
# --------------------------------------------------------------------------


def test_default_params_are_valid():
    DEFAULT_PARAMS.validate()


def test_baseline_conversion_is_the_product_of_the_rates():
    expected = math.prod(DEFAULT_PARAMS.base_transition_rates[k] for k in TRANSITION_KEYS)
    assert DEFAULT_PARAMS.baseline_conversion() == pytest.approx(expected)
    # Sanity: a plausible retail baseline.
    assert 0.01 < DEFAULT_PARAMS.baseline_conversion() < 0.05


@pytest.mark.parametrize(
    "overrides",
    [
        {"device_mix": {"mobile": 0.5, "desktop": 0.2}},
        {"segment_mix": {"loyal": 1.5}},
        {"base_transition_rates": {"visit->browse": 0.5}},
        {"weekday_weights": (1.0, 1.0)},
        {"hour_weights": (1.0,) * 12},
    ],
)
def test_validate_rejects_malformed_params(overrides):
    with pytest.raises(ValueError):
        replace(DEFAULT_PARAMS, **overrides).validate()


def test_validate_rejects_effects_on_unknown_transitions():
    params = replace(
        DEFAULT_PARAMS,
        interventions={
            "bogus": InterventionParams(key="bogus", description="x", effects={"a->b": 1.1})
        },
        experiments=(),
    )
    with pytest.raises(ValueError, match="unknown transitions"):
        params.validate()


def test_validate_rejects_variant_weights_that_do_not_sum_to_one():
    params = replace(
        DEFAULT_PARAMS,
        experiments=(
            ExperimentSpec(
                key="broken",
                variants=(("control", 0.4), ("treatment", 0.4)),
                variant_interventions={"control": (), "treatment": ()},
            ),
        ),
    )
    with pytest.raises(ValueError, match="sum to 1"):
        params.validate()


def test_params_round_trip_to_a_json_safe_dict():
    payload = DEFAULT_PARAMS.to_dict()
    assert payload["seed"] == DEFAULT_PARAMS.seed
    # Stored on every simulation_runs row, so it must be plain data.
    import json

    assert json.loads(json.dumps(payload, default=str))["sessions"] == DEFAULT_PARAMS.sessions


# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------


def test_same_seed_reproduces_the_run_exactly():
    first, second = simulate(small()), simulate(small())
    assert first.truth == second.truth
    assert len(first.events) == len(second.events)
    assert first.sessions["converted"].tolist() == second.sessions["converted"].tolist()


def test_different_seeds_produce_different_runs():
    assert (
        simulate(small(seed=1)).sessions["converted"].sum()
        != simulate(small(seed=2)).sessions["converted"].sum()
    )


# --------------------------------------------------------------------------
# The honesty guarantees
# --------------------------------------------------------------------------


def test_aa_configuration_has_exactly_zero_population_effect():
    # The analytic truth is computed, not sampled, so this must be exact.
    truth = simulate(aa_params(sessions=2_000)).truth
    assert truth["expected_relative_lift"] == pytest.approx(0.0, abs=1e-12)
    assert truth["expected_absolute_lift"] == pytest.approx(0.0, abs=1e-12)


def test_population_truth_equals_the_configured_compound_effect():
    # assistant 1.015 x 1.025, nudges 1.025 x 1.012 => 1.0792
    expected = 1.015 * 1.025 * 1.025 * 1.012 - 1.0
    truth = simulate(small()).truth
    assert truth["expected_relative_lift"] == pytest.approx(expected, rel=1e-6)


def test_an_effect_lands_on_exactly_the_transition_it_was_configured_for():
    """A single large effect must show up at its own step and nowhere else."""
    spec = ExperimentSpec(
        key="flagship_assistant_nudges",
        variants=(("control", 0.5), ("treatment", 0.5)),
        variant_interventions={"control": (), "treatment": ("solo",)},
    )
    params = replace(
        DEFAULT_PARAMS,
        sessions=120_000,
        interventions={
            "solo": InterventionParams(
                key="solo", description="x", effects={"product_view->add_to_cart": 1.5}
            )
        },
        experiments=(spec,),
    )
    sessions = simulate(params).sessions
    control = sessions[sessions["variant_flagship_assistant_nudges"] == "control"]
    treatment = sessions[sessions["variant_flagship_assistant_nudges"] == "treatment"]

    def conditional_rate(frame, step_index: int) -> float:
        reached = (frame["step_depth"] >= step_index).sum()
        advanced = (frame["step_depth"] >= step_index + 1).sum()
        return advanced / reached if reached else 0.0

    for index, _ in enumerate(FUNNEL_ORDER[:-1]):
        ratio = conditional_rate(treatment, index) / conditional_rate(control, index)
        if FUNNEL_ORDER[index] == "product_view":
            assert ratio == pytest.approx(1.5, rel=0.06), "configured effect not recovered"
        else:
            # Deep steps carry few sessions, so the band widens down the funnel.
            tolerance = 0.06 if index < 3 else 0.20
            assert ratio == pytest.approx(
                1.0, rel=tolerance
            ), f"unconfigured effect leaked into {FUNNEL_ORDER[index]}"


def test_assignment_split_is_balanced():
    sessions = simulate(replace(DEFAULT_PARAMS, sessions=40_000)).sessions
    share = (sessions["variant_flagship_assistant_nudges"] == "treatment").mean()
    assert abs(share - 0.5) < 0.02


# --------------------------------------------------------------------------
# Output shape
# --------------------------------------------------------------------------


def test_events_conform_to_the_shared_event_schema():
    from cartiq_api.schemas import Device, EventType, TrafficSource

    events = simulate(small()).events
    assert set(events["event_type"]) <= {e.value for e in EventType}
    assert set(events["device"]) <= {d.value for d in Device}
    assert set(events["traffic_source"]) <= {t.value for t in TrafficSource}
    assert events["session_id"].notna().all()
    assert events["timestamp"].notna().all()
    # Simulated sessions DO observe device and attribution, unlike the import.
    assert "unknown" not in set(events["device"])


def test_every_session_emits_a_session_start_and_timestamps_advance():
    output = simulate(small())
    starts = output.events[output.events["event_type"] == "session_start"]
    assert len(starts) == len(output.sessions)

    ordered = output.events.sort_values(["session_id", "timestamp"])
    for _, group in ordered.groupby("session_id"):
        assert group["timestamp"].is_monotonic_increasing


def test_only_converting_sessions_emit_a_purchase():
    output = simulate(small())
    purchased = set(output.events.loc[output.events["event_type"] == "purchase", "session_id"])
    converted = set(output.sessions.loc[output.sessions["converted"], "session_id"])
    assert purchased == converted


def test_nudges_are_only_shown_to_the_treatment_arm():
    output = simulate(small())
    nudges = output.events[output.events["event_type"] == "nudge_shown"]
    assert len(nudges) > 0
    variants = {a.get("flagship_assistant_nudges") for a in nudges["experiment_assignments"]}
    assert variants == {"treatment"}


def test_experiment_assignments_are_stamped_on_every_event():
    events = simulate(small()).events
    assert all("flagship_assistant_nudges" in a for a in events["experiment_assignments"])


def test_simulated_carts_use_the_supplied_catalog():
    import pandas as pd

    catalog = pd.DataFrame(
        {"product_id": ["real-1", "real-2"], "price": [9.99, 24.5], "units_sold": [100, 10]}
    )
    events = simulate(small(), catalog).events
    seen = set(events["product_id"].dropna())
    assert seen <= {"real-1", "real-2"}
    assert seen
