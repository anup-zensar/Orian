"""Database engine, session factory and declarative base (spec §5.1, §6).

SQLite is the demo default; ``DATABASE_URL`` keeps the engine swappable (Azure SQL / PostgreSQL later).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app import clock
from app.config import BACKEND_DIR, get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class TimestampMixin:
    """Every table gets ``created_at`` / ``updated_at`` (spec §6)."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now, onupdate=clock.now)


SessionLocal = sessionmaker(autoflush=False, expire_on_commit=False)
_engine: Engine | None = None


def _resolve_url(url: str) -> str:
    """Make relative SQLite paths (``sqlite:///./orion.db``) relative to ``backend/``."""
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith("sqlite:////"):
        path = url[len(prefix) :]
        if path and path != ":memory:" and not (len(path) > 1 and path[1] == ":"):
            # relative path (no drive letter) -> anchor at backend/
            return prefix + (BACKEND_DIR / path).resolve().as_posix()
    return url


def configure_engine(url: str | None = None) -> Engine:
    """(Re)create the engine. Called at startup and by tests with a temporary database URL."""
    global _engine
    resolved = _resolve_url(url or get_settings().database_url)
    connect_args: dict[str, object] = {}
    if resolved.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(resolved, connect_args=connect_args)
    if resolved.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    SessionLocal.configure(bind=_engine)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        return configure_engine()
    return _engine


def create_all() -> None:
    from app import models  # noqa: F401 - register all tables

    Base.metadata.create_all(get_engine())


def drop_all() -> None:
    from app import models  # noqa: F401 - register all tables

    Base.metadata.drop_all(get_engine())


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
