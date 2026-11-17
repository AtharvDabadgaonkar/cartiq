"""Health and wiring endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from cartiq_api import __version__
from cartiq_api.config import get_settings
from cartiq_api.db import ping

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Service health payload."""

    status: str
    version: str
    database: str
    llm_provider: str
    phase: int


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report liveness and whether the database is reachable."""
    settings = get_settings()
    database_up = ping()
    return HealthResponse(
        status="ok" if database_up else "degraded",
        version=__version__,
        database="up" if database_up else "down",
        llm_provider=settings.llm_provider,
        phase=5,
    )
