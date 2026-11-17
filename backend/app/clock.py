"""Demo clock (PLAN.md A-15).

All business code must call ``today()`` / ``now()`` from here instead of ``date.today()`` or
``datetime.now()``, so the demo "Set today" control (spec §8.16) and ``SEED_DATE`` work everywhere.

Precedence: admin override (Demo controls) -> ``SEED_DATE`` -> real date.
``now()`` combines ``today()`` with the real time of day, so timestamps stay coherent after the
demo date has been moved.
"""

from __future__ import annotations

from datetime import date, datetime

from app.config import get_settings

_today_override: date | None = None


def set_today_override(value: date | None) -> None:
    """Set (or clear with ``None``) the in-process demo date. Persisted by the admin endpoint."""
    global _today_override
    _today_override = value


def get_today_override() -> date | None:
    return _today_override


def today() -> date:
    if _today_override is not None:
        return _today_override
    seed_date = get_settings().seed_date
    if seed_date is not None:
        return seed_date
    return date.today()  # noqa: DTZ011 - the only place the real date is read


def now() -> datetime:
    """Naive local timestamp on the demo date (stored as-is in SQLite)."""
    real = datetime.now()  # noqa: DTZ005 - the only place the real time is read
    return datetime.combine(today(), real.time()).replace(microsecond=0)
