"""Schema introspection, so the console can document its own contract."""

from fastapi import APIRouter
from pydantic import BaseModel

from cartiq_api.schemas import FUNNEL_STEPS, Device, EventType, TrafficSource

router = APIRouter(prefix="/schema", tags=["schema"])


class FunnelStepOut(BaseModel):
    """One funnel step, as served to the console."""

    key: str
    label: str
    event_type: str


class SchemaResponse(BaseModel):
    """The event contract this service expects."""

    event_types: list[str]
    devices: list[str]
    traffic_sources: list[str]
    funnel: list[FunnelStepOut]


@router.get("", response_model=SchemaResponse)
def event_schema() -> SchemaResponse:
    """Return the event contract, for the metrics dictionary UI."""
    return SchemaResponse(
        event_types=[e.value for e in EventType],
        devices=[d.value for d in Device],
        traffic_sources=[t.value for t in TrafficSource],
        funnel=[
            FunnelStepOut(key=s.key, label=s.label, event_type=s.event_type.value)
            for s in FUNNEL_STEPS
        ],
    )
