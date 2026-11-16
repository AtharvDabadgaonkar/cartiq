"""Streamlit entrypoint for the CartIQ internal console.

Streamlit Community Cloud runs the file at the repository root, so this module
only wires up the path and hands off to `apps/console`.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
# Importable locally without installing the workspace; on Streamlit Cloud the
# analytics package comes from requirements.txt (./apps/api).
for extra in (REPO_ROOT / "apps" / "api" / "src", REPO_ROOT / "apps" / "console"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from cartiq_console.app import main  # noqa: E402

main()
