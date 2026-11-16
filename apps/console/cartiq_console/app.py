"""Console navigation and shell."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from cartiq_console import __version__
from cartiq_console.sections import SECTIONS

PAGES_DIR = Path(__file__).resolve().parents[1] / "pages"


def main() -> None:
    """Configure the app and run the selected page."""
    st.set_page_config(
        page_title="CartIQ Console",
        page_icon="🔶",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    with st.sidebar:
        st.markdown("### 🔶 CartIQ")
        st.caption("Conversion Intelligence Console")
        st.caption(f"v{__version__} · Phase 1 of 9")

    pages = [
        st.Page(
            str(PAGES_DIR / f"{section.key}.py"),
            title=section.label,
            icon=section.icon,
            url_path=section.key.replace("_", "-"),
            default=section.key == "overview",
        )
        for section in SECTIONS
    ]

    st.navigation(pages).run()
