"""Streamlit entrypoint for the CartIQ internal console.

Streamlit Community Cloud runs the file at the repository root, so this module
only wires up the path and hands off to `apps/console`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
# Importable locally without installing the workspace; on Streamlit Cloud the
# analytics package comes from requirements.txt (./apps/api).
for extra in (REPO_ROOT / "apps" / "api" / "src", REPO_ROOT / "apps" / "console"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def _bridge_secrets() -> None:
    """Copy Streamlit secrets into the environment before settings are read.

    `cartiq_api.config` reads plain environment variables so the same code runs
    locally, in CI and on a server. Streamlit Cloud supplies configuration
    through `st.secrets`, so the two are bridged here rather than teaching the
    settings layer about Streamlit.
    """
    import streamlit as st

    try:
        secrets = st.secrets
    except Exception:  # no secrets file locally, which is fine
        return

    for key in ("DATABASE_URL", "LLM_PROVIDER", "FLAG_HASH_SALT", "EMBEDDING_DIM"):
        try:
            value = secrets.get(key)
        except Exception:
            value = None
        if value and not os.environ.get(key):
            os.environ[key] = str(value)


_bridge_secrets()

from cartiq_console.app import main  # noqa: E402

main()
