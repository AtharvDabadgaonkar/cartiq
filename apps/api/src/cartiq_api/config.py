"""Validated settings for the analytics service.

Mirrors apps/web/lib/env.ts so the two halves of the app cannot drift on
defaults that matter (the assignment salt above all: a mismatch would silently
invalidate every experiment).
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: apps/api/src/cartiq_api/config.py -> ../../../..
REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env", override=False)


class Settings(BaseSettings):
    """Service configuration, read from the environment."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = Field(
        default="postgresql://cartiq:cartiq@localhost:5433/cartiq",
        alias="DATABASE_URL",
    )
    api_cors_origins: str = Field(default="http://localhost:3000", alias="API_CORS_ORIGINS")
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    embedding_dim: int = Field(default=384, alias="EMBEDDING_DIM")

    # Must equal FLAG_HASH_SALT on the web side, or assignment diverges.
    flag_hash_salt: str = Field(default="cartiq-v1", alias="FLAG_HASH_SALT")

    sim_seed: int = Field(default=42, alias="SIM_SEED")
    sim_sessions: int = Field(default=60_000, alias="SIM_SESSIONS")

    @property
    def cors_origins(self) -> list[str]:
        """CORS origins as a list."""
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """Database URL with the psycopg3 driver and Prisma-only params stripped."""
        url = self.database_url.split("?")[0]
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
