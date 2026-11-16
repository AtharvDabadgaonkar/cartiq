"""Simulator parameters.

Everything the simulator believes about shopper behaviour lives here, as data.
Nothing is hard-coded in the engine, and `SimulationParams.to_dict()` is stored
on every `simulation_runs` row, so any simulated figure can be traced to the
exact assumptions that produced it.

Plain-language justification for each value is in docs/SIMULATION.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

#: The seven transitions of the canonical funnel. Each is the probability of
#: advancing from one step to the next, for a baseline session.
FUNNEL_TRANSITIONS: tuple[tuple[str, str], ...] = (
    ("visit", "browse"),
    ("browse", "product_view"),
    ("product_view", "add_to_cart"),
    ("add_to_cart", "checkout"),
    ("checkout", "shipping"),
    ("shipping", "payment"),
    ("payment", "purchase"),
)

TRANSITION_KEYS: tuple[str, ...] = tuple(f"{a}->{b}" for a, b in FUNNEL_TRANSITIONS)


@dataclass(frozen=True)
class InterventionParams:
    """One shippable intervention and the effect it is assumed to have.

    Attributes:
        key: Feature-flag key gating the intervention.
        description: What the shopper actually sees.
        effects: {transition_key: multiplier} applied to the advance
            probability. 1.0 means no effect; 1.12 means a 12% relative lift.
        eligible_devices: Restrict the effect, empty tuple meaning all devices.
        guardrail_effects: {metric: multiplier} for side effects worth watching,
            e.g. a nudge that lifts conversion but also lifts returns.
    """

    key: str
    description: str
    effects: dict[str, float]
    eligible_devices: tuple[str, ...] = ()
    guardrail_effects: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentSpec:
    """An experiment the simulator should assign traffic to.

    The engine assigns variants with the same FNV-1a function the storefront
    uses, so assignment is identical on both sides.
    """

    key: str
    variants: tuple[tuple[str, float], ...]
    #: Intervention keys switched on for each variant.
    variant_interventions: dict[str, tuple[str, ...]]
    exposure: float = 1.0


@dataclass(frozen=True)
class SimulationParams:
    """Complete, reproducible description of a simulation run."""

    seed: int = 42
    # Sized so the flagship experiment is actually powered to detect its own
    # effect. The realised baseline is ~1.6% once the device, segment and
    # traffic multipliers are applied, and a 7.9% relative lift on that
    # baseline needs ~159k sessions per variant for 80% power at alpha 0.05.
    # 500k total gives ~250k per variant, i.e. roughly 90% power.
    sessions: int = 500_000
    start_date: str = "2026-01-05"
    days: int = 56

    # --- Population mix -----------------------------------------------------
    device_mix: dict[str, float] = field(
        default_factory=lambda: {"mobile": 0.62, "desktop": 0.31, "tablet": 0.07}
    )
    traffic_mix: dict[str, float] = field(
        default_factory=lambda: {
            "organic": 0.31,
            "paid_search": 0.22,
            "direct": 0.18,
            "email": 0.13,
            "social": 0.11,
            "referral": 0.05,
        }
    )
    #: Behavioural segments. Shares must sum to 1.
    segment_mix: dict[str, float] = field(
        default_factory=lambda: {
            "new_visitor": 0.46,
            "returning_browser": 0.30,
            "loyal": 0.16,
            "bargain_hunter": 0.08,
        }
    )
    #: Distinct users, so returning visitors genuinely repeat.
    users: int = 120_000

    # --- Baseline funnel ----------------------------------------------------
    #: Probability of advancing each step for a baseline session. The product of
    #: these is the baseline session conversion rate.
    base_transition_rates: dict[str, float] = field(
        default_factory=lambda: {
            "visit->browse": 0.78,
            "browse->product_view": 0.54,
            "product_view->add_to_cart": 0.21,
            "add_to_cart->checkout": 0.52,
            "checkout->shipping": 0.81,
            "shipping->payment": 0.74,
            "payment->purchase": 0.88,
        }
    )
    device_multipliers: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            # Mobile browses as much but converts worse once money is involved:
            # the single biggest real-world friction pattern in commerce.
            "mobile": {
                "add_to_cart->checkout": 0.88,
                "checkout->shipping": 0.84,
                "shipping->payment": 0.80,
                "payment->purchase": 0.93,
            },
            "desktop": {},
            "tablet": {"shipping->payment": 0.94},
        }
    )
    segment_multipliers: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "new_visitor": {"product_view->add_to_cart": 0.82, "add_to_cart->checkout": 0.88},
            "returning_browser": {"product_view->add_to_cart": 1.0},
            "loyal": {
                "browse->product_view": 1.18,
                "product_view->add_to_cart": 1.35,
                "add_to_cart->checkout": 1.22,
            },
            "bargain_hunter": {
                "product_view->add_to_cart": 1.15,
                "add_to_cart->checkout": 0.74,
            },
        }
    )
    traffic_multipliers: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "email": {"product_view->add_to_cart": 1.20, "add_to_cart->checkout": 1.10},
            "paid_search": {"product_view->add_to_cart": 1.05},
            "social": {"browse->product_view": 0.88, "product_view->add_to_cart": 0.80},
            "organic": {},
            "direct": {"add_to_cart->checkout": 1.08},
            "referral": {},
        }
    )

    # --- Economics ----------------------------------------------------------
    #: Items per cart ~ 1 + Poisson(lambda).
    cart_items_lambda: float = 1.6
    #: Orders above this get free shipping.
    free_shipping_threshold: float = 40.0
    shipping_cost: float = 4.95
    #: Relative drop in checkout completion when shipping is charged. Applied at
    #: add_to_cart->checkout, where the cost first becomes visible.
    shipping_cost_penalty: float = 0.82
    #: Elasticity on cart value: each doubling of basket value multiplies
    #: checkout completion by this. Below 1 means expensive carts hesitate more.
    price_sensitivity: float = 0.94
    #: Baseline probability an order is later returned (guardrail metric).
    base_return_rate: float = 0.071

    # --- Seasonality --------------------------------------------------------
    #: Monday..Sunday traffic weights.
    weekday_weights: tuple[float, ...] = (1.08, 1.05, 1.02, 1.0, 0.98, 0.82, 0.86)
    #: Relative session volume by hour of day.
    hour_weights: tuple[float, ...] = (
        0.25,
        0.16,
        0.11,
        0.09,
        0.10,
        0.18,
        0.38,
        0.62,
        0.86,
        1.02,
        1.12,
        1.18,
        1.20,
        1.16,
        1.12,
        1.10,
        1.14,
        1.26,
        1.38,
        1.44,
        1.36,
        1.10,
        0.72,
        0.42,
    )

    # --- Interventions ------------------------------------------------------
    interventions: dict[str, InterventionParams] = field(
        default_factory=lambda: {
            "ai_shopping_assistant": InterventionParams(
                key="ai_shopping_assistant",
                description=(
                    "Catalog-grounded chat assistant. Helps shoppers find a matching "
                    "product and compare options, so more browsing turns into a "
                    "product view and more product views turn into a cart add."
                ),
                # Sized to be realistic, not flattering: published assistant
                # trials land in the low single digits per step. A 20%+ lift
                # would make the experiment significant on any sample and
                # demonstrate nothing about the statistics.
                effects={
                    "browse->product_view": 1.015,
                    "product_view->add_to_cart": 1.025,
                },
            ),
            "cart_recovery_nudges": InterventionParams(
                key="cart_recovery_nudges",
                description=(
                    "Risk-triggered nudges in the cart: distance to the free-shipping "
                    "threshold, saved-cart reminder, low-stock note. Targets the "
                    "cart-to-checkout drop, which is where the money leaks."
                ),
                effects={
                    "add_to_cart->checkout": 1.025,
                    "shipping->payment": 1.012,
                },
                # Nudges that push hesitant shoppers over the line also push up
                # returns slightly. This is the guardrail the readout must catch.
                guardrail_effects={"return_rate": 1.06},
            ),
            "personalised_recommendations": InterventionParams(
                key="personalised_recommendations",
                description=(
                    "Item-to-item co-occurrence recommendations with a popular-items "
                    "fallback for new users."
                ),
                effects={"browse->product_view": 1.02},
            ),
        }
    )

    # --- Experiments --------------------------------------------------------
    experiments: tuple[ExperimentSpec, ...] = field(
        default_factory=lambda: (
            ExperimentSpec(
                key="flagship_assistant_nudges",
                variants=(("control", 0.5), ("treatment", 0.5)),
                variant_interventions={
                    "control": (),
                    "treatment": ("ai_shopping_assistant", "cart_recovery_nudges"),
                },
            ),
        )
    )

    #: Salt for assignment. Must match FLAG_HASH_SALT on the web side.
    assignment_salt: str = "cartiq-v1"

    def validate(self) -> None:
        """Fail loudly on a malformed parameter set."""
        for name, mix in (
            ("device_mix", self.device_mix),
            ("traffic_mix", self.traffic_mix),
            ("segment_mix", self.segment_mix),
        ):
            total = sum(mix.values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"{name} must sum to 1, got {total}")

        missing = set(TRANSITION_KEYS) - set(self.base_transition_rates)
        if missing:
            raise ValueError(f"base_transition_rates missing {sorted(missing)}")
        for key, rate in self.base_transition_rates.items():
            if not 0 < rate <= 1:
                raise ValueError(f"base rate {key}={rate} must be in (0, 1]")

        for intervention in self.interventions.values():
            unknown = set(intervention.effects) - set(TRANSITION_KEYS)
            if unknown:
                raise ValueError(
                    f"{intervention.key} targets unknown transitions {sorted(unknown)}"
                )

        for spec in self.experiments:
            weight_total = sum(weight for _, weight in spec.variants)
            if abs(weight_total - 1.0) > 1e-6:
                raise ValueError(f"{spec.key} variant weights must sum to 1, got {weight_total}")
            for variant, keys in spec.variant_interventions.items():
                if variant not in {name for name, _ in spec.variants}:
                    raise ValueError(f"{spec.key} maps unknown variant {variant}")
                unknown_keys = set(keys) - set(self.interventions)
                if unknown_keys:
                    raise ValueError(f"{spec.key}/{variant} uses unknown {sorted(unknown_keys)}")

        if len(self.weekday_weights) != 7:
            raise ValueError("weekday_weights must have 7 entries")
        if len(self.hour_weights) != 24:
            raise ValueError("hour_weights must have 24 entries")

    def baseline_conversion(self) -> float:
        """Product of the baseline transition rates: the headline baseline CVR."""
        result = 1.0
        for key in TRANSITION_KEYS:
            result *= self.base_transition_rates[key]
        return result

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable form, stored on the simulation_runs row."""
        return asdict(self)


DEFAULT_PARAMS = SimulationParams()
