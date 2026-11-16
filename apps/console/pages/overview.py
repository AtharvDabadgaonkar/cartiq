"""Overview.

Phase 9 turns this into the one-screen story (top friction point → intervention
shipped → experiment result → next bet). Until the data is loaded it reports
what is wired up instead of showing placeholder figures, which would breach the
no-invented-metrics rule.
"""

from __future__ import annotations

import streamlit as st

from cartiq_console.data import database_available, row_counts
from cartiq_console.sections import SECTIONS
from cartiq_console.theme import data_source_badge

st.title("Overview")

connected = database_available()

if not connected:
    st.warning(
        "No database connection. Set `DATABASE_URL` and run `make db-up && make migrate`. "
        "The console still renders so the structure can be reviewed."
    )
    counts: dict[str, int] = {}
else:
    try:
        counts = row_counts()
    except Exception as error:  # noqa: BLE001 - surface, never crash the page
        st.warning(
            f"Schema not migrated yet ({type(error).__name__}). Run `make migrate`."
        )
        counts = {}

total_events = counts.get("events", 0)
data_source_badge("none" if total_events == 0 else "mixed")

left, middle, right = st.columns(3)
left.metric("Events ingested", f"{total_events:,}")
middle.metric("Catalog products", f"{counts.get('products', 0):,}")
right.metric("LLM calls logged", f"{counts.get('llm_calls', 0):,}")

if total_events:
    st.caption(
        f"Real dataset: {counts.get('real_events', 0):,} · "
        f"Simulated: {counts.get('simulated_events', 0):,} · "
        f"Demo traffic: {counts.get('demo_events', 0):,}"
    )

st.divider()
st.subheader("What is wired up")
st.markdown(
    """
- **Event pipeline** — one event schema (Zod on the client, Pydantic on the service, Prisma
  enums in the database, with a parity test that fails the build on drift), a batching tracking
  SDK with client-side validation, and an idempotent ingest endpoint.
- **Deterministic assignment** — FNV-1a hash bucketing pinned to shared cross-language test
  vectors, so the TypeScript storefront and the Python simulator assign identically. Exposure
  ramping uses a separate hash namespace, so going 1% → 10% never reassigns an exposed user.
- **Pluggable LLM** — one provider interface with a grounding-faithful mock as the default, and
  every call logged with the exact context it was given.
- **Provenance as a column** — every event row is `REAL_DATASET`, `SIMULATED` or `LIVE_DEMO`,
  and every surface here reports which sources its numbers cover.
"""
)

st.subheader("Coming sections")
for row in range(0, len(SECTIONS), 2):
    columns = st.columns(2)
    for column, section in zip(columns, SECTIONS[row : row + 2], strict=False):
        if section.key == "overview":
            continue
        with column.container(border=True):
            st.markdown(
                f"**{section.label}** &nbsp; :gray-badge[Phase {section.phase}]"
            )
            st.caption(section.blurb)
