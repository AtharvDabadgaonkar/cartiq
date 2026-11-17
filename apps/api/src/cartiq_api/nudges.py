"""Cart-recovery nudge engine.

Rules, not a model. The model produces a calibrated risk score; these rules
decide what — if anything — to say about it. Keeping the decision explicit
means a merchandiser can read why a shopper saw a message, and a PM can turn
one off without retraining anything.

Every nudge is gated by its own feature flag, so they ramp and roll back
independently.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Risk above which a cart is worth interrupting at all. Chosen from the
#: calibrated score, not from the classifier's 0.5 default: with an ~80% base
#: abandonment rate, 0.5 would fire on virtually every cart and the nudge would
#: stop meaning anything.
HIGH_RISK_THRESHOLD = 0.85
MEDIUM_RISK_THRESHOLD = 0.75

#: Below this gap, telling a shopper what free delivery costs them is useful
#: rather than annoying.
FREE_SHIPPING_NUDGE_GAP = 15.0


@dataclass(frozen=True)
class Nudge:
    """One message the cart can show."""

    key: str
    flag: str
    headline: str
    body: str
    #: Why this fired, surfaced in the console so the rule is auditable.
    rationale: str


@dataclass(frozen=True)
class CartContext:
    """What the engine knows about a cart when it decides."""

    cart_value: float
    items: int
    risk_score: float
    pays_shipping: bool
    gap_to_free_shipping: float
    is_returning_visitor: bool = False


#: Flag keys, one per nudge, so each can be ramped or killed on its own.
NUDGE_FLAGS: tuple[str, ...] = (
    "nudge_free_shipping",
    "nudge_saved_cart",
    "nudge_low_stock",
)


def choose_nudge(context: CartContext, enabled_flags: frozenset[str]) -> Nudge | None:
    """Pick at most one nudge for a cart.

    At most one on purpose: stacking three messages on a hesitant shopper is
    how a helpful nudge becomes a dark pattern, and it would also make the
    experiment uninterpretable — you could not say which message moved anyone.

    Order is by usefulness to the shopper, not by expected lift: a concrete,
    actionable fact ("you are £4 from free delivery") beats a generic reminder.
    """
    if context.risk_score < MEDIUM_RISK_THRESHOLD:
        return None

    if (
        "nudge_free_shipping" in enabled_flags
        and context.pays_shipping
        and 0 < context.gap_to_free_shipping <= FREE_SHIPPING_NUDGE_GAP
    ):
        return Nudge(
            key="free_shipping_threshold",
            flag="nudge_free_shipping",
            headline=f"£{context.gap_to_free_shipping:.2f} from free delivery",
            body="Add a little more and delivery is on us.",
            rationale=(
                f"risk {context.risk_score:.0%} >= {MEDIUM_RISK_THRESHOLD:.0%} and the cart is "
                f"£{context.gap_to_free_shipping:.2f} short of the £40 threshold"
            ),
        )

    if "nudge_saved_cart" in enabled_flags and context.risk_score >= HIGH_RISK_THRESHOLD:
        return Nudge(
            key="saved_cart_reminder",
            flag="nudge_saved_cart",
            headline="Your cart is saved",
            body="Take your time — these items will still be here when you come back.",
            rationale=f"risk {context.risk_score:.0%} >= {HIGH_RISK_THRESHOLD:.0%}",
        )

    if "nudge_low_stock" in enabled_flags and context.items > 1:
        return Nudge(
            key="low_stock_note",
            flag="nudge_low_stock",
            headline="Popular right now",
            body="Items in your cart are selling quickly today.",
            rationale=(
                f"risk {context.risk_score:.0%} >= {MEDIUM_RISK_THRESHOLD:.0%} "
                f"with {context.items} items and no better-matching nudge"
            ),
        )

    return None


def describe_rules() -> list[dict[str, str]]:
    """The rule ladder, for the console. Documentation that cannot drift."""
    return [
        {
            "order": "0",
            "nudge": "none",
            "flag": "—",
            "condition": f"risk < {MEDIUM_RISK_THRESHOLD:.0%}",
            "message": "Say nothing. Most carts are not worth interrupting.",
        },
        {
            "order": "1",
            "nudge": "free_shipping_threshold",
            "flag": "nudge_free_shipping",
            "condition": (
                f"risk >= {MEDIUM_RISK_THRESHOLD:.0%}, shipping is charged, and the cart is "
                f"within £{FREE_SHIPPING_NUDGE_GAP:.0f} of the threshold"
            ),
            "message": "Tell them exactly how far they are from free delivery.",
        },
        {
            "order": "2",
            "nudge": "saved_cart_reminder",
            "flag": "nudge_saved_cart",
            "condition": f"risk >= {HIGH_RISK_THRESHOLD:.0%}",
            "message": "Reduce pressure: the cart will still be there.",
        },
        {
            "order": "3",
            "nudge": "low_stock_note",
            "flag": "nudge_low_stock",
            "condition": f"risk >= {MEDIUM_RISK_THRESHOLD:.0%} and more than one item",
            "message": "Mild urgency, only when nothing more useful applies.",
        },
    ]
