"""The TypeScript schema is the source of truth; this guards against drift.

A silent divergence between packages/shared and the Pydantic/Prisma mirrors
would corrupt every downstream metric, so it fails the build instead.
"""

import re
from pathlib import Path

from cartiq_api.schemas import FUNNEL_STEPS, Device, EventType, TrafficSource

REPO_ROOT = Path(__file__).resolve().parents[3]
PRISMA_SCHEMA = REPO_ROOT / "apps" / "web" / "prisma" / "schema.prisma"


def _string_array(source: str, name: str) -> list[str]:
    """Extract the string literals from `export const NAME = [...] as const`."""
    match = re.search(rf"export const {name} = \[(.*?)\] as const", source, re.DOTALL)
    assert match, f"{name} not found in events.ts"
    return re.findall(r"'([^']+)'", match.group(1))


def _prisma_enum(name: str) -> list[str]:
    source = PRISMA_SCHEMA.read_text()
    match = re.search(rf"^enum {name} \{{(.*?)^\}}", source, re.DOTALL | re.MULTILINE)
    assert match, f"enum {name} not found in schema.prisma"
    body = re.sub(r"///.*", "", match.group(1))
    return [line.strip() for line in body.splitlines() if line.strip()]


def test_event_types_match_typescript(shared_events_ts):
    assert _string_array(shared_events_ts, "EVENT_TYPES") == [e.value for e in EventType]


def test_devices_match_typescript(shared_events_ts):
    assert _string_array(shared_events_ts, "DEVICES") == [d.value for d in Device]


def test_traffic_sources_match_typescript(shared_events_ts):
    assert _string_array(shared_events_ts, "TRAFFIC_SOURCES") == [t.value for t in TrafficSource]


def test_funnel_steps_match_typescript(shared_events_ts):
    match = re.search(
        r"export const FUNNEL_STEPS = \[(.*?)\] as const", shared_events_ts, re.DOTALL
    )
    assert match
    ts_keys = re.findall(r"key: '([^']+)'", match.group(1))
    ts_event_types = re.findall(r"eventType: '([^']+)'", match.group(1))
    assert ts_keys == [s.key for s in FUNNEL_STEPS]
    assert ts_event_types == [s.event_type.value for s in FUNNEL_STEPS]


def test_prisma_event_type_enum_matches():
    assert _prisma_enum("EventType") == [e.value for e in EventType]


def test_prisma_device_and_source_enums_match():
    assert _prisma_enum("DeviceType") == [d.value for d in Device]
    assert _prisma_enum("TrafficSource") == [t.value for t in TrafficSource]
