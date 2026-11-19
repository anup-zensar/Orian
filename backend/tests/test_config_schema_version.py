"""CR-01 design 3: the database schema version is checked at startup (ensure_schema_version)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select, text

from app import db as database
from app.config import get_settings
from app.db import SCHEMA_VERSION, SessionLocal, ensure_schema_version, stored_schema_version
from app.models import AppSetting, Portfolio, User


def _set_version(value: int | None) -> None:
    with SessionLocal() as db:
        if value is None:
            db.execute(text("DELETE FROM app_settings WHERE key = 'schema_version'"))
        else:
            db.merge(AppSetting(key="schema_version", value=value))
        db.commit()


def test_seed_writes_the_current_schema_version(client, fresh_seed) -> None:
    assert SCHEMA_VERSION >= 3  # 3 = CR-01 simplification
    assert stored_schema_version() == SCHEMA_VERSION


def test_equal_version_keeps_modified_data(client, fresh_seed) -> None:
    with SessionLocal() as db:
        db.get(Portfolio, "GCC").label = "Changed label"
        db.commit()
    assert ensure_schema_version() is False
    with SessionLocal() as db:
        assert db.get(Portfolio, "GCC").label == "Changed label"


@pytest.mark.parametrize("stored", [1, 2, SCHEMA_VERSION + 5, None])
def test_other_version_rebuilds_and_reseeds(client, fresh_seed, stored: int | None) -> None:
    """Older, newer than the code, or missing: drop, re-create, re-seed (demo data is synthetic)."""
    with SessionLocal() as db:
        db.get(Portfolio, "GCC").label = "Changed label"
        db.commit()
    _set_version(stored)
    assert ensure_schema_version() is True
    assert stored_schema_version() == SCHEMA_VERSION
    with SessionLocal() as db:
        assert db.get(Portfolio, "GCC").label == "GCC"
        assert db.scalar(select(User).where(User.id == "U16")) is not None


def test_auto_reset_disabled_gives_a_clear_error(client, fresh_seed, monkeypatch) -> None:
    _set_version(1)
    monkeypatch.setattr(get_settings(), "schema_auto_reset", False)
    with pytest.raises(RuntimeError, match="SCHEMA_AUTO_RESET"):
        ensure_schema_version()
    # nothing was dropped
    assert stored_schema_version() == 1


def test_fresh_database_needs_nothing(client, tmp_path) -> None:
    """No app_settings table: not a version problem (create_all + seed follow)."""
    try:
        database.configure_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
        assert stored_schema_version() is None
        assert ensure_schema_version() is False
    finally:
        database.configure_engine()  # back to the test database (DATABASE_URL)


def test_version_row_is_a_number(client, fresh_seed) -> None:
    with database.get_engine().connect() as conn:
        raw = conn.execute(
            text("SELECT value FROM app_settings WHERE key='schema_version'")
        ).scalar()
    assert int(json.loads(raw)) == SCHEMA_VERSION if isinstance(raw, str) else raw == SCHEMA_VERSION
