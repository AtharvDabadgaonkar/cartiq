"""Session generation.

The engine walks each simulated session down the funnel, multiplying a baseline
advance probability by the modifiers that apply to that session: device,
segment, traffic source, basket economics, and — only for sessions assigned to a
treatment variant — the configured intervention effects.

It deliberately knows nothing about statistics. It produces events; recovering
the effect from them is the Experiment Studio's job, and the test suite asserts
that the recovered interval contains the configured truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from cartiq_api.assignment import VariantSplit, assign_variant
from cartiq_api.simulation.params import (
    FUNNEL_TRANSITIONS,
    SimulationParams,
)

#: Event emitted on arriving at each funnel step.
STEP_EVENTS: dict[str, str] = {
    "visit": "session_start",
    "browse": "page_view",
    "product_view": "product_view",
    "add_to_cart": "add_to_cart",
    "checkout": "checkout_start",
    "shipping": "shipping_step",
    "payment": "payment_step",
    "purchase": "purchase",
}

STEP_PAGES: dict[str, str] = {
    "visit": "/",
    "browse": "/search",
    "product_view": "/product",
    "add_to_cart": "/cart",
    "checkout": "/checkout",
    "shipping": "/checkout/shipping",
    "payment": "/checkout/payment",
    "purchase": "/checkout/confirm",
}


@dataclass
class SimulationOutput:
    """Everything one simulation run produced."""

    events: pd.DataFrame
    #: One row per session, for assertions and for the readout's denominators.
    sessions: pd.DataFrame
    params: SimulationParams
    #: Ground truth. Not secret — every parameter is documented in
    #: docs/SIMULATION.md and stored on the simulation_runs row for
    #: reproducibility. The point is that the Experiment Studio never *reads*
    #: it: the estimate has to come from the generated events alone.
    #:
    #: `expected_*` are exact population parameters, computed analytically over
    #: the generated population rather than measured from the realisation, so a
    #: test can assert the estimator's interval covers the true value with no
    #: Monte Carlo noise in the target itself. `realised_*` are what this
    #: particular run happened to produce, which is what an analyst would see.
    truth: dict[str, float]


def _weighted_choice(rng: np.random.Generator, mix: dict[str, float], size: int) -> np.ndarray:
    keys = list(mix)
    probabilities = np.array([mix[k] for k in keys], dtype=float)
    probabilities /= probabilities.sum()
    return rng.choice(keys, size=size, p=probabilities)


def _timestamps(rng: np.random.Generator, params: SimulationParams, size: int) -> np.ndarray:
    """Draw session start times with weekday and hour-of-day seasonality."""
    start = datetime.fromisoformat(params.start_date)
    day_of_week = np.array([(start + timedelta(days=int(d))).weekday() for d in range(params.days)])
    day_weights = np.array([params.weekday_weights[w] for w in day_of_week], dtype=float)
    day_weights /= day_weights.sum()
    days = rng.choice(params.days, size=size, p=day_weights)

    hour_weights = np.array(params.hour_weights, dtype=float)
    hour_weights /= hour_weights.sum()
    hours = rng.choice(24, size=size, p=hour_weights)
    minutes = rng.integers(0, 60, size=size)
    seconds = rng.integers(0, 60, size=size)

    base = np.datetime64(start)
    return (
        base
        + days.astype("timedelta64[D]")
        + hours.astype("timedelta64[h]")
        + minutes.astype("timedelta64[m]")
        + seconds.astype("timedelta64[s]")
    )


def _transition_probability(
    transition: str,
    params: SimulationParams,
    device: str,
    segment: str,
    traffic: str,
    active_interventions: tuple[str, ...],
) -> float:
    """Advance probability for one session at one funnel transition."""
    probability = params.base_transition_rates[transition]
    probability *= params.device_multipliers.get(device, {}).get(transition, 1.0)
    probability *= params.segment_multipliers.get(segment, {}).get(transition, 1.0)
    probability *= params.traffic_multipliers.get(traffic, {}).get(transition, 1.0)

    for key in active_interventions:
        intervention = params.interventions[key]
        if intervention.eligible_devices and device not in intervention.eligible_devices:
            continue
        probability *= intervention.effects.get(transition, 1.0)

    return float(min(probability, 1.0))


def _assign_experiments(
    params: SimulationParams, user_id: str
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Assign this user's variants and resolve which interventions are live."""
    assignments: dict[str, str] = {}
    active: list[str] = []
    for spec in params.experiments:
        variant = assign_variant(
            user_id,
            spec.key,
            [VariantSplit(key, weight) for key, weight in spec.variants],
            params.assignment_salt,
            spec.exposure,
        )
        if variant is None:
            continue
        assignments[spec.key] = variant
        active.extend(spec.variant_interventions.get(variant, ()))
    return assignments, tuple(active)


def simulate(
    params: SimulationParams,
    catalog: pd.DataFrame | None = None,
    namespace: str | None = None,
) -> SimulationOutput:
    """Generate sessions and the events they produce.

    Args:
        params: Behavioural assumptions. See docs/SIMULATION.md.
        catalog: Optional real catalog (`product_id`, `price`, `units_sold`) so
            simulated carts contain real products at real prices. Without it,
            synthetic products are used and prices are drawn log-normally.
        namespace: Prefix for generated session and user ids. Two runs loaded
            into the same database MUST use different namespaces, or their
            sessions collide and merge into impossible ones.

    Returns:
        Events, per-session rows, the parameters, and the ground-truth effects
        the Experiment Studio is expected to recover.
    """
    params.validate()
    rng = np.random.default_rng(params.seed)
    n = params.sessions

    devices = _weighted_choice(rng, params.device_mix, n)
    traffic = _weighted_choice(rng, params.traffic_mix, n)
    segments = _weighted_choice(rng, params.segment_mix, n)
    started_at = _timestamps(rng, params, n)

    # Returning visitors reuse user ids, so RFM and CLV have repeat behaviour.
    user_numbers = rng.integers(0, params.users, size=n)
    prefix = f"{namespace}_" if namespace else ""
    user_ids = np.array([f"sim_{prefix}user_{u}" for u in user_numbers])

    if catalog is not None and not catalog.empty:
        product_ids = catalog["product_id"].to_numpy()
        product_prices = catalog["price"].astype(float).to_numpy()
        weights = catalog.get("units_sold")
        popularity = (
            np.maximum(weights.astype(float).to_numpy(), 1.0)
            if weights is not None
            else np.ones(len(catalog))
        )
        popularity = popularity / popularity.sum()
    else:
        product_ids = np.array([f"sim-sku-{i:04d}" for i in range(500)])
        product_prices = np.round(rng.lognormal(mean=2.5, sigma=0.6, size=500), 2)
        popularity = np.ones(500) / 500

    cart_sizes = 1 + rng.poisson(params.cart_items_lambda, size=n)

    event_rows: list[dict[str, object]] = []
    session_rows: list[dict[str, object]] = []
    step_names = ["visit", *[b for _, b in FUNNEL_TRANSITIONS]]

    # Ground truth. Realised counts, plus the exact per-session conversion
    # probability under each regime so the population parameter is known without
    # Monte Carlo error.
    truth_numerators: dict[str, list[float]] = {"control": [], "treatment": []}
    treatment_keys = _treatment_interventions(params)
    expected_control: list[float] = []
    expected_treatment: list[float] = []

    for i in range(n):
        user_id = str(user_ids[i])
        assignments, active = _assign_experiments(params, user_id)
        device, segment, source = str(devices[i]), str(segments[i]), str(traffic[i])
        session_id = f"sim_{prefix}sess_{i}"
        clock = pd.Timestamp(started_at[i], tz="UTC")

        # Basket is drawn up front so its economics can affect checkout.
        picks = rng.choice(len(product_ids), size=int(cart_sizes[i]), p=popularity)
        cart_value = float(np.sum(product_prices[picks]))
        pays_shipping = cart_value < params.free_shipping_threshold

        expected_control.append(
            _session_conversion_probability(
                params, device, segment, source, cart_value, pays_shipping, ()
            )
        )
        expected_treatment.append(
            _session_conversion_probability(
                params, device, segment, source, cart_value, pays_shipping, treatment_keys
            )
        )

        reached = "visit"
        event_rows.append(
            _event(
                session_id,
                user_id,
                "session_start",
                clock,
                device,
                source,
                segment,
                assignments,
                page=STEP_PAGES["visit"],
            )
        )

        for step_index, (origin, destination) in enumerate(FUNNEL_TRANSITIONS):
            transition = f"{origin}->{destination}"
            probability = _transition_probability(
                transition, params, device, segment, source, active
            )

            # Basket economics bite where the shopper first sees the total.
            if transition == "add_to_cart->checkout":
                if pays_shipping:
                    probability *= params.shipping_cost_penalty
                probability *= params.price_sensitivity ** np.log2(max(cart_value, 1.0) / 25.0)
                probability = float(min(probability, 1.0))

            if rng.random() >= probability:
                break

            clock = clock + pd.Timedelta(seconds=float(rng.gamma(2.0, 18.0)))
            reached = destination

            if destination == "product_view":
                product_index = int(picks[0])
                event_rows.append(
                    _event(
                        session_id,
                        user_id,
                        "product_view",
                        clock,
                        device,
                        source,
                        segment,
                        assignments,
                        page=f"/product/{product_ids[product_index]}",
                        product_id=str(product_ids[product_index]),
                        price=float(product_prices[product_index]),
                    )
                )
            elif destination == "add_to_cart":
                for product_index in picks:
                    event_rows.append(
                        _event(
                            session_id,
                            user_id,
                            "add_to_cart",
                            clock,
                            device,
                            source,
                            segment,
                            assignments,
                            page=STEP_PAGES["add_to_cart"],
                            product_id=str(product_ids[product_index]),
                            price=float(product_prices[product_index]),
                            quantity=1,
                        )
                    )
                if "cart_recovery_nudges" in active:
                    event_rows.append(
                        _event(
                            session_id,
                            user_id,
                            "nudge_shown",
                            clock,
                            device,
                            source,
                            segment,
                            assignments,
                            page=STEP_PAGES["add_to_cart"],
                            properties={
                                "nudge": "free_shipping_threshold"
                                if pays_shipping
                                else "saved_cart_reminder",
                                "gap_to_threshold": round(
                                    max(params.free_shipping_threshold - cart_value, 0.0), 2
                                ),
                            },
                        )
                    )
            elif destination == "purchase":
                event_rows.append(
                    _event(
                        session_id,
                        user_id,
                        "purchase",
                        clock,
                        device,
                        source,
                        segment,
                        assignments,
                        page=STEP_PAGES["purchase"],
                        price=round(
                            cart_value + (params.shipping_cost if pays_shipping else 0.0), 2
                        ),
                        quantity=int(cart_sizes[i]),
                        properties={"order_id": f"sim_ord_{i}", "items": int(cart_sizes[i])},
                    )
                )
            else:
                event_rows.append(
                    _event(
                        session_id,
                        user_id,
                        STEP_EVENTS[destination],
                        clock,
                        device,
                        source,
                        segment,
                        assignments,
                        page=STEP_PAGES[destination],
                    )
                )

            # Some browsing sessions use search rather than only navigating.
            # Emitted in addition to the page_view, because a shopper who
            # searches has also viewed the results page.
            if destination == "browse" and rng.random() < params.search_share:
                event_rows.append(
                    _event(
                        session_id,
                        user_id,
                        "search",
                        clock,
                        device,
                        source,
                        segment,
                        assignments,
                        page=STEP_PAGES["browse"],
                        properties={"source": "simulated"},
                    )
                )

            # The assistant is opened early, when the shopper starts looking.
            if (
                destination == "browse"
                and "ai_shopping_assistant" in active
                and rng.random() < 0.34
            ):
                event_rows.append(
                    _event(
                        session_id,
                        user_id,
                        "assistant_open",
                        clock,
                        device,
                        source,
                        segment,
                        assignments,
                        page=STEP_PAGES["browse"],
                    )
                )
            if destination == "browse" and "personalised_recommendations" in active:
                event_rows.append(
                    _event(
                        session_id,
                        user_id,
                        "recommendation_impression",
                        clock,
                        device,
                        source,
                        segment,
                        assignments,
                        page=STEP_PAGES["browse"],
                    )
                )
            del step_index

        converted = reached == "purchase"
        returned = bool(
            converted
            and rng.random()
            < params.base_return_rate * _guardrail_multiplier(params, active, "return_rate")
        )

        variant = assignments.get(params.experiments[0].key) if params.experiments else None
        if variant in truth_numerators:
            truth_numerators[variant].append(1.0 if converted else 0.0)

        session_rows.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "started_at": pd.Timestamp(started_at[i], tz="UTC"),
                "device": device,
                "traffic_source": source,
                "segment": segment,
                "reached_step": reached,
                "step_depth": step_names.index(reached),
                "converted": converted,
                "returned": returned,
                "cart_value": round(cart_value, 2),
                "paid_shipping": pays_shipping,
                **{f"variant_{k}": v for k, v in assignments.items()},
            }
        )

    events = (
        pd.DataFrame(event_rows).sort_values(["timestamp", "session_id"]).reset_index(drop=True)
    )
    sessions = pd.DataFrame(session_rows)

    control = float(np.mean(truth_numerators["control"])) if truth_numerators["control"] else 0.0
    treatment = (
        float(np.mean(truth_numerators["treatment"])) if truth_numerators["treatment"] else 0.0
    )
    expected_c = float(np.mean(expected_control)) if expected_control else 0.0
    expected_t = float(np.mean(expected_treatment)) if expected_treatment else 0.0
    truth = {
        "expected_control_conversion": round(expected_c, 8),
        "expected_treatment_conversion": round(expected_t, 8),
        "expected_absolute_lift": round(expected_t - expected_c, 8),
        "expected_relative_lift": round((expected_t / expected_c - 1.0) if expected_c else 0.0, 8),
        "realised_control_conversion": round(control, 6),
        "realised_treatment_conversion": round(treatment, 6),
        "realised_absolute_lift": round(treatment - control, 6),
        "realised_relative_lift": round((treatment / control - 1.0) if control else 0.0, 6),
    }

    return SimulationOutput(events=events, sessions=sessions, params=params, truth=truth)


def _treatment_interventions(params: SimulationParams) -> tuple[str, ...]:
    """Intervention keys switched on by the non-control variants of experiment 1."""
    if not params.experiments:
        return ()
    spec = params.experiments[0]
    keys: list[str] = []
    for variant, intervention_keys in spec.variant_interventions.items():
        if variant == "control":
            continue
        keys.extend(intervention_keys)
    return tuple(dict.fromkeys(keys))


def _session_conversion_probability(
    params: SimulationParams,
    device: str,
    segment: str,
    traffic: str,
    cart_value: float,
    pays_shipping: bool,
    active: tuple[str, ...],
) -> float:
    """Exact probability this session converts under a given intervention set.

    The funnel is a chain of independent Bernoulli steps given the session's
    fixed characteristics, so the end-to-end probability is their product.
    """
    probability = 1.0
    for origin, destination in FUNNEL_TRANSITIONS:
        transition = f"{origin}->{destination}"
        step = _transition_probability(transition, params, device, segment, traffic, active)
        if transition == "add_to_cart->checkout":
            if pays_shipping:
                step *= params.shipping_cost_penalty
            step *= params.price_sensitivity ** np.log2(max(cart_value, 1.0) / 25.0)
            step = min(step, 1.0)
        probability *= step
    return probability


def _guardrail_multiplier(params: SimulationParams, active: tuple[str, ...], metric: str) -> float:
    """Combined guardrail effect of the live interventions on one metric."""
    multiplier = 1.0
    for key in active:
        multiplier *= params.interventions[key].guardrail_effects.get(metric, 1.0)
    return multiplier


def _event(
    session_id: str,
    user_id: str,
    event_type: str,
    timestamp: pd.Timestamp,
    device: str,
    traffic_source: str,
    segment: str,
    assignments: dict[str, str],
    *,
    page: str,
    product_id: str | None = None,
    price: float | None = None,
    quantity: int | None = None,
    properties: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build one event row in the shape the loader expects."""
    payload: dict[str, object] = {"segment": segment}
    if properties:
        payload.update(properties)
    return {
        "event_type": event_type,
        "timestamp": timestamp,
        "user_id": user_id,
        "session_id": session_id,
        "device": device,
        "traffic_source": traffic_source,
        # Simulated sessions do model first-time visitors explicitly.
        "is_new_user": segment == "new_visitor",
        "page": page,
        "product_id": product_id,
        "price": price,
        "quantity": quantity,
        "experiment_assignments": assignments,
        "properties": payload,
    }
