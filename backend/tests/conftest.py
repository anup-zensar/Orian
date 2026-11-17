"""Shared pytest fixtures (PLAN.md section 4, M1.12).

The environment is configured BEFORE any ``app`` module reads its settings: a throw-away SQLite file
in a temp directory, no mock latency, a fixed demo date and a temp storage directory. Every test
therefore runs against the same deterministic seeded database (spec section 11), never against
``backend/orion.db``.

Fixtures other test modules can rely on:

* ``client``     - session-scoped ``TestClient(app)``; its lifespan creates the tables and seeds.
* ``db``         - a SQLAlchemy ``Session`` on the test database (function scoped, closed after).
* ``headers``    - helper ``headers("U14")`` -> ``{"X-Demo-User": "U14"}`` (default user ``U01``).
* ``fresh_seed`` - re-seeds the database before the test AND after it. Use it in every test that
  writes data; plain read tests share the seeded database and must not write.

Demo users: U01-U09 OR focals, U10 PM, U11 Architect, U12 OLM, U13 Planner, U14 IRM,
U15 Leadership, U16 Admin. The flagship transition is ``TR-0001`` (Mobility Knowledge Agent).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="orion-tests-"))
_STORAGE = _TMP_ROOT / "storage"
_STORAGE.mkdir()

# Must happen before app.config.get_settings() is first called (it is cached).
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_ROOT / 'orion_test.db').as_posix()}"
os.environ["MOCK_DELAY_MS"] = "0"
os.environ["SEED_DATE"] = "2026-11-16"
os.environ["DEMO_MODE"] = "true"
os.environ["STORAGE_DIR"] = str(_STORAGE)

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import clock  # noqa: E402
from app.db import SessionLocal, get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.loader import reset_and_seed  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """TestClient whose lifespan seeds the (temporary) database."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(client: TestClient) -> Iterator[Session]:
    """A session on the test database (depends on ``client`` so the engine and seed exist)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def headers() -> Callable[[str], dict[str, str]]:
    """``headers("U14")`` -> request headers that sign in as that demo user."""

    def _headers(user_id: str = "U01") -> dict[str, str]:
        return {"X-Demo-User": user_id}

    return _headers


@pytest.fixture
def fresh_seed(client: TestClient) -> Iterator[None]:
    """Pristine seeded data for tests that mutate; restored again afterwards."""
    reset_and_seed()
    yield
    reset_and_seed()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    clock.set_today_override(None)
    try:
        get_engine().dispose()
    finally:
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)
