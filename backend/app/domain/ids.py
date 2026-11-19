"""Sequential string identifiers (PLAN.md A-16): TR-0019, ACT-004, CON-003, EVD-004, EX-02, CR-15,
DEF-001, APR-0002.

Shared by every area. SQLite serialises writes, so a max+1 scan is safe for this single-process demo.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, Session

# prefix -> zero-padded width (keeps the seed's formats)
ID_FORMATS: dict[str, int] = {
    "TR-": 4,
    "ACT-": 3,
    "CON-": 3,
    "EVD-": 3,
    "EX-": 2,
    "CR-": 2,
    "DEF-": 3,
    "APR-": 4,
    "U": 2,  # users: U17, U18 ...
}


def next_id(db: Session, column: InstrumentedAttribute[str], prefix: str) -> str:
    """Next id for ``prefix`` in ``column`` (e.g. ``next_id(db, Action.id, "ACT-")`` -> "ACT-004")."""
    width = ID_FORMATS[prefix]
    existing = db.scalars(select(column).where(column.like(f"{prefix}%"))).all()
    numbers = [int(v[len(prefix) :]) for v in existing if v[len(prefix) :].isdigit()]
    return f"{prefix}{(max(numbers) + 1 if numbers else 1):0{width}d}"
