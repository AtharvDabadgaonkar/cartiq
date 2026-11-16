"""Shared pytest fixtures."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cartiq_api.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SRC = REPO_ROOT / "packages" / "shared" / "src"

# The Streamlit console lives outside apps/api but shares its test suite, so a
# drift between the two declarations of the console IA fails the build.
sys.path.insert(0, str(REPO_ROOT / "apps" / "console"))


@pytest.fixture(scope="session")
def client() -> TestClient:
    """FastAPI test client."""
    return TestClient(create_app())


@pytest.fixture(scope="session")
def assignment_vectors() -> dict[str, Any]:
    """Cross-language assignment vectors shared with the TypeScript suite."""
    path = SHARED_SRC / "__fixtures__" / "assignment-vectors.json"
    return json.loads(path.read_text())


@pytest.fixture(scope="session")
def shared_events_ts() -> str:
    """Raw text of the canonical TypeScript event schema."""
    return (SHARED_SRC / "events.ts").read_text()
