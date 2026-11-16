"""FastAPI application factory.

Phase 1 exposes health and schema introspection only; analytics, the ML models,
the stats engine and the simulator endpoints land in their own phases.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cartiq_api import __version__
from cartiq_api.config import get_settings
from cartiq_api.routers import health, schema


def create_app() -> FastAPI:
    """Build the application."""
    settings = get_settings()
    app = FastAPI(
        title="CartIQ Analytics API",
        version=__version__,
        description=(
            "Analytics, ML and experiment statistics for CartIQ. "
            "Numbers derived from simulated sessions are labelled as such in every response."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type", "authorization"],
    )
    app.include_router(health.router)
    app.include_router(schema.router)
    return app


app = create_app()
