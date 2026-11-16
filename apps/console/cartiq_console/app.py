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
        st.caption(f"v{__version__} · Phase 2 of 9")

    # The default page is served at "/", and Streamlit 404s a url_path set on
    # it, so only the other sections get an explicit path.
    pages: list[st.Page] = []
    for section in SECTIONS:
        path = str(PAGES_DIR / f"{section.key}.py")
        if section.key == "overview":
            pages.append(
                st.Page(path, title=section.label, icon=section.icon, default=True)
            )
        else:
            pages.append(
                st.Page(
                    path,
                    title=section.label,
                    icon=section.icon,
                    url_path=section.key.replace("_", "-"),
                )
            )

    st.navigation(pages).run()
