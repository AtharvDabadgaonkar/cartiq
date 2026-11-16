"""Database access for the analytics service.

Read-mostly by design: the web app owns writes through Prisma, and Module 6's
copilot is restricted to allow-listed read-only views.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from cartiq_api.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the lazily created process-wide engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_settings().sqlalchemy_url,
            pool_pre_ping=True,
            # Free-tier Postgres has a low connection ceiling.
            pool_size=5,
            max_overflow=5,
            future=True,
        )
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session, rolling back on error."""
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping() -> bool:
    """Return True when the database answers a trivial query."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # a health check must never raise
        return False
