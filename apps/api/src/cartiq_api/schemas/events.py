"""Event schema — the Python mirror of packages/shared/src/events.ts.

tests/test_schema_parity.py parses the TypeScript file and fails if the two
ever diverge, so this stays a mirror rather than a second source of truth.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(StrEnum):
    """Every tracked event. Order matches the TypeScript EVENT_TYPES array."""

    SESSION_START = "session_start"
    PAGE_VIEW = "page_view"
    SEARCH = "search"
    PRODUCT_VIEW = "product_view"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    CHECKOUT_START = "checkout_start"
    SHIPPING_STEP = "shipping_step"
    PAYMENT_STEP = "payment_step"
    PURCHASE = "purchase"
    ASSISTANT_OPEN = "assistant_open"
    ASSISTANT_QUERY = "assistant_query"
    ASSISTANT_CLICK = "assistant_click"
    RECOMMENDATION_IMPRESSION = "recommendation_impression"
    RECOMMENDATION_CLICK = "recommendation_click"
    NUDGE_SHOWN = "nudge_shown"
    NUDGE_CLICKED = "nudge_clicked"


class Device(StrEnum):
    """Device class, derived from the user agent."""

    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"


class TrafficSource(StrEnum):
    """Last-touch acquisition channel."""

    DIRECT = "direct"
    ORGANIC = "organic"
    PAID_SEARCH = "paid_search"
    SOCIAL = "social"
    EMAIL = "email"
    REFERRAL = "referral"


class DataSource(StrEnum):
    """Provenance of a row. Never report a mixed number without saying so."""

    REAL_DATASET = "REAL_DATASET"
    SIMULATED = "SIMULATED"
    LIVE_DEMO = "LIVE_DEMO"


PropertyValue = str | int | float | bool | None | list[str | int | float | bool | None]

#: Canonical UUID form. Event ids are client-generated, which is what makes
#: re-ingestion idempotent, so the format is enforced at the edge.
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class Event(BaseModel):
    """One tracked interaction."""

    model_config = ConfigDict(extra="forbid")

    event_id: Annotated[str, Field(pattern=UUID_PATTERN)]
    event_type: EventType
    timestamp: datetime
    user_id: str | None = Field(default=None, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)
    device: Device
    traffic_source: TrafficSource
    is_new_user: bool
    page: str = Field(min_length=1, max_length=512)
    product_id: str | None = Field(default=None, max_length=64)
    price: float | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, gt=0)
    experiment_assignments: dict[str, str] = Field(default_factory=dict)
    properties: dict[str, PropertyValue] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        """Reject naive timestamps: a funnel across timezones must be unambiguous."""
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone offset")
        return value


class EventBatch(BaseModel):
    """A batch as posted by the tracking SDK."""

    model_config = ConfigDict(extra="forbid")

    events: list[Event] = Field(min_length=1, max_length=100)
    sent_at: datetime


class FunnelStep(BaseModel):
    """One step of the canonical purchase funnel."""

    key: str
    label: str
    event_type: EventType


FUNNEL_STEPS: tuple[FunnelStep, ...] = (
    FunnelStep(key="visit", label="Visit", event_type=EventType.SESSION_START),
    FunnelStep(key="browse", label="Search / Browse", event_type=EventType.PAGE_VIEW),
    FunnelStep(key="product_view", label="Product View", event_type=EventType.PRODUCT_VIEW),
    FunnelStep(key="add_to_cart", label="Add to Cart", event_type=EventType.ADD_TO_CART),
    FunnelStep(key="checkout", label="Checkout Start", event_type=EventType.CHECKOUT_START),
    FunnelStep(key="shipping", label="Shipping", event_type=EventType.SHIPPING_STEP),
    FunnelStep(key="payment", label="Payment", event_type=EventType.PAYMENT_STEP),
    FunnelStep(key="purchase", label="Purchase", event_type=EventType.PURCHASE),
)

#: Both of these advance the "browse" step.
BROWSE_EVENT_TYPES: tuple[EventType, ...] = (EventType.PAGE_VIEW, EventType.SEARCH)

FunnelStepKey = Literal[
    "visit", "browse", "product_view", "add_to_cart", "checkout", "shipping", "payment", "purchase"
]
