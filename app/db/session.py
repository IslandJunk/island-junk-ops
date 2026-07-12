"""Lazy engine/session so the app can import and serve /health without a DB."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Register every model on Base.metadata so cross-table FKs always resolve for any
# session user (scripts, app). Safe from cycles: models never import this module.
import app.models.all  # noqa: E402,F401

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _normalize_db_url(url: str) -> str:
    """Force the psycopg 3 driver. We install `psycopg[binary]` (psycopg 3), but a bare
    `postgres://` / `postgresql://` URL (what Render's managed Postgres injects) makes
    SQLAlchemy reach for psycopg2, which isn't installed → boot crash. Rewriting the scheme
    to `postgresql+psycopg://` makes the app deploy-portable no matter how the URL is given.
    A URL that already names a driver (`postgresql+psycopg://`, `...+psycopg2://`, etc.) is
    left untouched."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def _init() -> None:
    global _engine, _SessionLocal
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not set — copy .env.example to .env and fill it in."
            )
        _engine = create_engine(
            _normalize_db_url(settings.database_url), pool_pre_ping=True, future=True
        )
        _SessionLocal = sessionmaker(
            bind=_engine, autoflush=False, autocommit=False, class_=Session
        )


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    _init()
    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def new_session() -> Session:
    """A plain Session for scripts/seeding (caller must close)."""
    _init()
    assert _SessionLocal is not None
    return _SessionLocal()
