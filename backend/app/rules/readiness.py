"""Readiness and progress (BR-020, spec §7.3; A-09, A-22, A-32, A-33). PURE.

Per lens, for a transition at gate ``G``:

* scope  = items with applicability ``Applies``, due at or before ``G``, status not N/A
  (``To confirm`` items are outside scope until confirmed, A-22)
* done   = scope items in a done status OR ``covered`` (open condition due after ``G``, or an
  approved exception - computed by the caller, A-09/A-33)
* open gaps = scope items in a gap status that are not covered; critical = severity Critical
* readiness = round-half-up(100 * done / scope), 100 when the scope is empty
* overall = round-half-up(mean of the three lens values)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from app.rules.constants import (
    APPLIES,
    DONE_STATUSES,
    GAP_STATUSES,
    GATE_ORDER,
    IN_PROGRESS_STATUSES,
    LENSES,
    NA_STATUSES,
    NOT_STARTED,
)


def round_half_up(value: float | int | Fraction | Decimal) -> int:
    """Round .5 up (A-32). Python's ``round`` is banker's rounding (2.5 -> 2): never use it for %.

    Floats are read through their shortest repr, so 12.5 -> 13 and 0.5 -> 1. Pass a ``Fraction``
    when the value is a ratio of integers to stay exact.
    """
    if isinstance(value, Fraction):
        return (value + Fraction(1, 2)).__floor__()
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def percent(done: int, scope: int) -> int:
    """100 x done / scope, round-half-up, exact (integers only); 100 for an empty scope."""
    if scope <= 0:
        return 100
    return round_half_up(Fraction(100 * done, scope))


@dataclass(frozen=True)
class ReadinessItem:
    lens: str
    due_gate: str
    applicability: str
    status: str
    gap_severity: str | None = None
    covered: bool = False  # open condition due after the gate, or approved exception


@dataclass(frozen=True)
class LensReadiness:
    scope: int
    done: int
    in_progress: int
    not_started: int
    open_gaps: int
    critical_gaps: int
    readiness_pct: int

    def to_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Readiness:
    lenses: dict[str, LensReadiness]
    overall: int
    totals: dict[str, int]

    @property
    def lens_pct(self) -> dict[str, int]:
        return {lens: r.readiness_pct for lens, r in self.lenses.items()}

    @property
    def open_gaps(self) -> int:
        return self.totals["open_gaps"]

    @property
    def critical_gaps(self) -> int:
        return self.totals["critical_gaps"]

    def to_dict(self) -> dict[str, object]:
        return {
            "lenses": {k: v.to_dict() for k, v in self.lenses.items()},
            "overall": self.overall,
            "totals": dict(self.totals),
        }


def in_scope(item: ReadinessItem, gate: str) -> bool:
    """BR-020 scope rule for one item at current gate ``gate``."""
    return (
        item.applicability == APPLIES
        and GATE_ORDER[item.due_gate] <= GATE_ORDER[gate]
        and item.status not in NA_STATUSES
    )


def compute_readiness(items: Iterable[ReadinessItem], gate: str) -> Readiness:
    if gate not in GATE_ORDER:
        raise ValueError(f"Unknown gate {gate!r}")
    buckets = {lens: [0, 0, 0, 0, 0, 0] for lens in LENSES}  # scope, done, prog, new, gaps, crit
    for item in items:
        if item.lens not in buckets or not in_scope(item, gate):
            continue
        b = buckets[item.lens]
        b[0] += 1
        if item.status in DONE_STATUSES or item.covered:
            b[1] += 1
        elif item.status in GAP_STATUSES:
            b[4] += 1
            if item.gap_severity == "Critical":
                b[5] += 1
        elif item.status in IN_PROGRESS_STATUSES:
            b[2] += 1
        elif item.status == NOT_STARTED:
            b[3] += 1

    lenses = {
        lens: LensReadiness(
            scope=b[0],
            done=b[1],
            in_progress=b[2],
            not_started=b[3],
            open_gaps=b[4],
            critical_gaps=b[5],
            readiness_pct=percent(b[1], b[0]),
        )
        for lens, b in buckets.items()
    }
    overall = round_half_up(Fraction(sum(r.readiness_pct for r in lenses.values()), len(lenses)))
    totals = {
        key: sum(getattr(r, key) for r in lenses.values())
        for key in ("scope", "done", "in_progress", "not_started", "open_gaps", "critical_gaps")
    }
    return Readiness(lenses=lenses, overall=overall, totals=totals)
