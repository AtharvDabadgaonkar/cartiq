"""Shared renderer for sections whose build phase has not shipped yet.

Each section still gets its own page module (Streamlit requires a distinct
script per page), so a phase replaces exactly one file when it ships.
"""

from __future__ import annotations

import streamlit as st

from cartiq_console.sections import SECTIONS_BY_KEY


def render_placeholder(key: str) -> None:
    """Describe what this section will contain, without inventing figures."""
    section = SECTIONS_BY_KEY[key]
    st.title(section.label)
    st.badge(f"Arrives in Phase {section.phase}", color="gray")
    st.write(section.blurb)
    st.divider()
    st.caption(
        "No placeholder figures are shown here on purpose: every number in CartIQ is produced "
        "by `make metrics` into reports/metrics.json, with its provenance attached."
    )
