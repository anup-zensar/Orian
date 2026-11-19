"""Database engine, session factory and declarative base (spec §5.1, §6).

SQLite is the demo default; ``DATABASE_URL`` keeps the engine swappable (Azure SQL / PostgreSQL later).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app import clock
from app.config import BACKEND_DIR, get_settings

logger = logging.getLogger("orion.db")

# Bump on EVERY model change (new table / column). Version 1 = M1-M9 + CR-02; 2 = CR-01 configuration
# tables and columns. The demo database is rebuilt and re-seeded when it differs (ensure_schema_version).
SCHEMA_VERSION = 2
SCHEMA_VERSION_KEY = "schema_version"  # app_settings key, written LAST by the seed loader


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


def stored_schema_version() -> int | None:
    """The version recorded in ``app_settings`` (1 when the table exists but has no row), or None
    when the database is fresh (no ``app_settings`` table)."""
    engine = get_engine()
    if not inspect(engine).has_table("app_settings"):
        return None
    try:
        with engine.connect() as conn:
            raw = conn.execute(
                text("SELECT value FROM app_settings WHERE key = :k"), {"k": SCHEMA_VERSION_KEY}
            ).scalar()
        if raw is None:
            return 1
        # a JSON column holding a bare number comes back as a number from raw SQL, else as text
        return int(raw) if isinstance(raw, int | float) else int(json.loads(raw))
    except Exception:  # unreadable or malformed row: treat like "no version recorded"
        return 1


def ensure_schema_version() -> bool:
    """CR-01 design 3: compare the stored schema version with ``SCHEMA_VERSION``.

    * fresh database (no ``app_settings`` table): nothing to do (``create_all`` + seed follow);
    * equal: nothing to do (modified demo data is kept);
    * different (older, or newer than this code): drop everything, re-create and re-seed - the
      demo data is synthetic. ``SCHEMA_AUTO_RESET=false`` raises a clear error instead.

    Returns True when the database was rebuilt. Called by the app lifespan before ``create_all``.
    """
    stored = stored_schema_version()
    if stored is None or stored == SCHEMA_VERSION:
        return False
    if not get_settings().schema_auto_reset:
        raise RuntimeError(
            f"Database schema version {stored} does not match the code (version {SCHEMA_VERSION}) "
            "and SCHEMA_AUTO_RESET is false. Migrate the database, or set SCHEMA_AUTO_RESET=true "
            "to re-create it (this deletes all data)."
        )
    logger.warning(
        "Demo database schema v%s is not v%s: re-creating and re-seeding (demo data is synthetic)",
        stored,
        SCHEMA_VERSION,
    )
    from app.seed.loader import reset_and_seed  # late import: the loader imports this module

    reset_and_seed()
    return True


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
