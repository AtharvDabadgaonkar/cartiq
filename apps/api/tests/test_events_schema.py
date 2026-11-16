"""Pydantic validation must reject exactly what Zod rejects."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from cartiq_api.schemas import BROWSE_EVENT_TYPES, FUNNEL_STEPS, Event, EventBatch, EventType

VALID = {
    "event_id": "6f1b8c2e-4a2d-4f1a-9c3b-0d5e7a9b1c2d",
    "event_type": "add_to_cart",
    "timestamp": "2026-03-01T12:00:00+00:00",
    "user_id": "user_42",
    "session_id": "sess_1",
    "device": "mobile",
    "traffic_source": "paid_search",
    "is_new_user": False,
    "page": "/product/sku-1",
    "product_id": "sku-1",
    "price": 59.99,
    "quantity": 1,
}


def test_valid_event_defaults_open_maps():
    event = Event.model_validate(VALID)
    assert event.experiment_assignments == {}
    assert event.properties == {}
    assert event.event_type is EventType.ADD_TO_CART


def test_rejects_unknown_event_type():
    with pytest.raises(ValidationError):
        Event.model_validate({**VALID, "event_type": "wishlist_add"})


def test_rejects_naive_timestamp():
    with pytest.raises(ValidationError, match="timezone"):
        Event.model_validate({**VALID, "timestamp": "2026-03-01T12:00:00"})


def test_rejects_non_uuid_event_id():
    with pytest.raises(ValidationError):
        Event.model_validate({**VALID, "event_id": "evt-1"})


@pytest.mark.parametrize(("field", "value"), [("price", -1), ("quantity", 0)])
def test_rejects_impossible_numbers(field, value):
    with pytest.raises(ValidationError):
        Event.model_validate({**VALID, field: value})


def test_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Event.model_validate({**VALID, "utm_campaign": "spring"})


def test_allows_anonymous_visitor_but_requires_session():
    assert Event.model_validate({**VALID, "user_id": None}).user_id is None
    without_session = {k: v for k, v in VALID.items() if k != "session_id"}
    with pytest.raises(ValidationError):
        Event.model_validate(without_session)


def test_batch_bounds():
    now = datetime.now(UTC).isoformat()
    with pytest.raises(ValidationError):
        EventBatch.model_validate({"events": [], "sent_at": now})
    with pytest.raises(ValidationError):
        EventBatch.model_validate({"events": [VALID] * 101, "sent_at": now})
    assert len(EventBatch.model_validate({"events": [VALID], "sent_at": now}).events) == 1


def test_funnel_is_well_formed():
    keys = [step.key for step in FUNNEL_STEPS]
    assert len(set(keys)) == len(keys)
    assert keys[0] == "visit"
    assert keys[-1] == "purchase"
    assert EventType.SEARCH in BROWSE_EVENT_TYPES
