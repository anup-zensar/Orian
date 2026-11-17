"""OCET projection maths and variance (BR-070, spec 7.9). Pure functions, no I/O. Implemented in M6.

Rules:
* Years = ``start_year .. start_year + horizon_years - 1``.
* ``amount[start_year] = base_amount``; later years compound:
  ``amount[y] = amount[y-1] * (1 + g_y / 100)`` where ``g_y = year_overrides[y]`` if present
  else ``growth_pct``. Full precision is kept; only display helpers round.
* A line with ``base_amount is None`` contributes 0 in every year and sets ``inputs_pending``.
* Worked example (unit test): 100,000 at 10% -> 100,000, 110,000, 121,000, 133,100, 146,410.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


@dataclass(frozen=True)
class OcetLineInput:
    """Plain input for one line (build from OcetLine; keys of year_overrides may be str or int)."""

    line_key: str
    category: str
    base_amount: float | None
    growth_pct: float = 0.0
    year_overrides: Mapping[str | int, float] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class LineProjection:
    line_key: str
    category: str
    description: str
    base_missing: bool
    yearly: dict[int, float]  # year -> amount (all zeros when base_missing)
    total: float  # sum over the horizon


@dataclass(frozen=True)
class Projection:
    years: list[int]
    lines: list[LineProjection]  # same order as the input lines
    category_totals: dict[str, dict[int, float]]  # category -> year -> amount (first-seen order)
    category_grand: dict[str, float]  # category -> horizon total
    grand_total_by_year: dict[int, float]
    total: float  # horizon total
    inputs_pending: bool  # any line has base_amount None


@dataclass(frozen=True)
class VarianceRow:
    """One variance row. ``status``: added (only in current) | removed (only in previous) |
    changed (abs change above 0.005) | same."""

    key: str  # line_key for by-line rows, category name for by-category rows
    category: str
    description: str
    previous_total: float
    current_total: float
    abs_change: float  # current - previous
    pct_change: float | None  # None when previous_total == 0
    status: str


@dataclass(frozen=True)
class Variance:
    total_abs: float
    total_pct: float | None
    by_category: list[VarianceRow]
    by_line: list[VarianceRow]


def years_for(start_year: int, horizon_years: int) -> list[int]:
    """``[start_year, ..., start_year + horizon_years - 1]``."""
    return [start_year + i for i in range(max(horizon_years, 0))]


def _normalised_overrides(overrides: Mapping[str | int, float]) -> dict[int, float]:
    out: dict[int, float] = {}
    for key, value in (overrides or {}).items():
        try:
            out[int(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def project_line(line: OcetLineInput, start_year: int, horizon_years: int) -> LineProjection:
    """Project one line over the horizon (see module docstring). Override keys are normalised with
    ``int(key)``; an override for a year outside the horizon is ignored. Overrides apply to the
    growth INTO that year (e.g. override {2028: 30} sets amount[2028] = amount[2027] * 1.30).
    """
    years = years_for(start_year, horizon_years)
    if line.base_amount is None:
        return LineProjection(
            line_key=line.line_key,
            category=line.category,
            description=line.description,
            base_missing=True,
            yearly={y: 0.0 for y in years},
            total=0.0,
        )
    overrides = _normalised_overrides(line.year_overrides)
    yearly: dict[int, float] = {}
    amount = float(line.base_amount)
    for index, year in enumerate(years):
        if index > 0:
            growth = overrides.get(year, line.growth_pct)
            amount = amount * (1 + growth / 100.0)
        yearly[year] = amount
    return LineProjection(
        line_key=line.line_key,
        category=line.category,
        description=line.description,
        base_missing=False,
        yearly=yearly,
        total=sum(yearly.values()),
    )


def project_version(
    lines: Sequence[OcetLineInput], start_year: int, horizon_years: int
) -> Projection:
    """Project all lines: per-line yearly amounts, totals by category x year, grand total by year,
    horizon total and ``inputs_pending`` (True when any ``base_amount`` is None). Empty list gives
    zero totals and ``inputs_pending=False``.
    """
    years = years_for(start_year, horizon_years)
    projected = [project_line(line, start_year, horizon_years) for line in lines]
    category_totals: dict[str, dict[int, float]] = {}
    for proj in projected:
        bucket = category_totals.setdefault(proj.category, {y: 0.0 for y in years})
        for year, amount in proj.yearly.items():
            bucket[year] += amount
    category_grand = {c: sum(v.values()) for c, v in category_totals.items()}
    grand_by_year = {y: sum(v[y] for v in category_totals.values()) for y in years}
    return Projection(
        years=years,
        lines=projected,
        category_totals=category_totals,
        category_grand=category_grand,
        grand_total_by_year=grand_by_year,
        total=sum(grand_by_year.values()),
        inputs_pending=any(p.base_missing for p in projected),
    )


def _row(
    key: str, category: str, description: str, previous: float, current: float, presence: str
) -> VarianceRow:
    change = current - previous
    pct = None if previous == 0 else change / previous * 100.0
    if presence in ("added", "removed"):
        status = presence
    else:
        status = "changed" if abs(change) > 0.005 else "same"
    return VarianceRow(key, category, description, previous, current, change, pct, status)


def variance(previous: Projection | None, current: Projection) -> Variance:
    """Variance of ``current`` vs ``previous`` per line (matched by ``line_key``) and per category.

    ``previous is None`` -> every row has previous_total 0, status "added" and the totals are
    abs=current.total, pct=None. Lines only in previous are "removed" (current_total 0). Rows are
    ordered: current lines in order, then removed ones. ``pct_change`` = abs / previous_total * 100
    (None when previous_total == 0).
    """
    prev_lines = {p.line_key: p for p in previous.lines} if previous else {}
    by_line: list[VarianceRow] = []
    for line in current.lines:
        before = prev_lines.get(line.line_key)
        by_line.append(
            _row(
                line.line_key,
                line.category,
                line.description,
                before.total if before else 0.0,
                line.total,
                "both" if before else "added",
            )
        )
    current_keys = {line.line_key for line in current.lines}
    for key, before in prev_lines.items():
        if key not in current_keys:
            by_line.append(
                _row(key, before.category, before.description, before.total, 0.0, "removed")
            )

    prev_cats = previous.category_grand if previous else {}
    by_category: list[VarianceRow] = []
    for cat, total in current.category_grand.items():
        presence = "both" if cat in prev_cats else "added"
        by_category.append(_row(cat, cat, "", prev_cats.get(cat, 0.0), total, presence))
    for cat, total in prev_cats.items():
        if cat not in current.category_grand:
            by_category.append(_row(cat, cat, "", total, 0.0, "removed"))

    prev_total = previous.total if previous else 0.0
    total_abs = current.total - prev_total
    total_pct = None if prev_total == 0 else total_abs / prev_total * 100.0
    return Variance(total_abs, total_pct, by_category, by_line)


def format_k(amount: float) -> str:
    """Display in thousands with one decimal: 146410 -> "146.4k", 100000 -> "100.0k", 0 -> "0.0k",
    999 -> "1.0k"; negatives keep the sign ("-12.5k").
    """
    try:
        value = Decimal(str(amount)) / Decimal(1000)
        rounded = value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return "n/a"  # inf / NaN / beyond Decimal precision
    if rounded == 0:
        rounded = Decimal("0.0")
    return f"{rounded}k"


def format_total_label(amount: float) -> str:
    """Compact label for headers/cards: >= 1,000,000 -> millions with 2 decimals ("1.92M"),
    otherwise ``format_k``.
    """
    if amount != amount:  # NaN
        return "n/a"
    if abs(amount) >= 1_000_000:
        try:
            value = (Decimal(str(amount)) / Decimal(1_000_000)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        except (InvalidOperation, ValueError):
            return "n/a"
        return f"{value}M"
    return format_k(amount)
