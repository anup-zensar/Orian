"""Deterministic status synthesis (spec §11.3, A-07, A-08, A-36). PURE.

Turns a snapshot (readiness % per lens, open gaps, critical gaps) into concrete item statuses so a
seeded transition reproduces the snapshot numbers when BR-020 is computed on it.

Pinned items (flagship overrides, A-08, plus items referenced by seeded open conditions, A-36) keep
their given status; they count towards the done / gap targets, and the remaining "free" items are
filled around them.

Steps per call:
 1. scope_L = Applies items due at or before the current gate, sorted by (gate order, id)
 2. target_done_L = round-half-up(pct_L / 100 x |scope_L|); pinned-done and covered items count
    towards it, then the first free items become done
 3. gap budget = snapshot.open_gaps - pinned gap items, split across lenses by their remaining free
    counts (largest remainder, ties by lens order Business, Technical, Compliance); the LAST free
    items of each lens become Gap / Non-compliant (Major)
 4. critical: preferred ids that are gaps first, then the lowest (gate, id) gap items, until
    snapshot.critical_gaps items are Critical
 5. remaining free in-scope items -> In progress / In review; items due after the gate -> Not started
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from app.rules.constants import (
    APPLIES,
    DONE_STATUSES,
    GAP_STATUSES,
    GATE_ORDER,
    LENSES,
    NOT_STARTED,
    done_status_for,
    gap_status_for,
    in_progress_status_for,
)
from app.rules.readiness import round_half_up

DE_NONE = "–"  # design effectiveness not assessed (Compliance items only)


@dataclass(frozen=True)
class SynthItem:
    id: str
    lens: str
    due_gate: str
    applicability: str = APPLIES


@dataclass(frozen=True)
class Snapshot:
    readiness_pct: Mapping[str, int]
    open_gaps: int
    critical_gaps: int


@dataclass(frozen=True)
class Pin:
    """A fixed status for one item. Severity / design effectiveness default sensibly when None."""

    status: str
    gap_severity: str | None = None
    design_effectiveness: str | None = None


@dataclass(frozen=True)
class SynthResult:
    status: str
    gap_severity: str | None
    design_effectiveness: str | None


def _sort_key(item: SynthItem) -> tuple[int, str]:
    return (GATE_ORDER[item.due_gate], item.id)


def _design_effectiveness(lens: str, status: str) -> str | None:
    """Compliance done -> Yes; other Compliance -> "–"; Business/Technical -> None."""
    if lens != "Compliance":
        return None
    return "Yes" if status in DONE_STATUSES else DE_NONE


def _split_budget(budget: int, free_counts: Mapping[str, int]) -> dict[str, int]:
    """Largest-remainder split of ``budget`` over lenses proportionally to their free counts."""
    total = sum(free_counts.values())
    quotas = {lens: 0 for lens in LENSES}
    if budget <= 0 or total <= 0:
        return quotas
    budget = min(budget, total)  # cannot have more gaps than free items
    remainders: list[tuple[int, int, str]] = []
    for order, lens in enumerate(LENSES):
        numerator = budget * free_counts.get(lens, 0)
        quotas[lens] = numerator // total
        remainders.append((-(numerator % total), order, lens))  # largest remainder, then lens order
    leftover = budget - sum(quotas.values())
    for _, _, lens in sorted(remainders)[:leftover]:
        quotas[lens] += 1
    return quotas


def synthesize(
    items: Iterable[SynthItem],
    current_gate: str,
    snapshot: Snapshot,
    pinned: Mapping[str, Pin] | None = None,
    covered_item_ids: Collection[str] = (),
    preferred_critical_ids: Sequence[str] = (),
) -> dict[str, SynthResult]:
    """Return {item id: SynthResult} for every ``Applies`` item (other items are not returned)."""
    pinned = pinned or {}
    covered = set(covered_item_ids)
    gate_order = GATE_ORDER[current_gate]
    applicable = sorted((i for i in items if i.applicability == APPLIES), key=_sort_key)

    results: dict[str, SynthResult] = {}
    severity: dict[str, str | None] = {}  # gap item id -> severity (later adjusted for Critical)
    gap_ids: list[str] = []  # all gap items in scope, pinned and synthesised

    def put(item: SynthItem, status: str, sev: str | None = None, de: str | None = None) -> None:
        results[item.id] = SynthResult(
            status=status,
            gap_severity=sev,
            design_effectiveness=de if de is not None else _design_effectiveness(item.lens, status),
        )

    # Pinned items keep their status wherever they are (in scope or not).
    for item in applicable:
        pin = pinned.get(item.id)
        if pin is None:
            continue
        sev = pin.gap_severity or ("Major" if pin.status in GAP_STATUSES else None)
        put(item, pin.status, sev, pin.design_effectiveness)

    # Items due after the current gate have not started (unless pinned).
    scope: dict[str, list[SynthItem]] = {lens: [] for lens in LENSES}
    for item in applicable:
        if GATE_ORDER[item.due_gate] > gate_order:
            if item.id not in results:
                put(item, NOT_STARTED)
        elif item.lens in scope:
            scope[item.lens].append(item)
        else:
            raise ValueError(f"Unknown lens {item.lens!r} on {item.id}")

    free: dict[str, list[SynthItem]] = {}
    pinned_gaps = 0
    for lens, lens_scope in scope.items():
        done_count = 0
        free[lens] = []
        for item in lens_scope:
            existing = results.get(item.id)
            if existing is not None:  # pinned
                if existing.status in DONE_STATUSES or item.id in covered:
                    done_count += 1
                if existing.status in GAP_STATUSES:
                    pinned_gaps += 1
                    gap_ids.append(item.id)
                    severity[item.id] = existing.gap_severity
            elif item.id in covered:  # covered by an open condition / approved exception
                put(item, done_status_for(lens))
                done_count += 1
            else:
                free[lens].append(item)

        target_done = round_half_up(
            Fraction(snapshot.readiness_pct.get(lens, 100) * len(lens_scope), 100)
        )
        need_done = min(max(0, target_done - done_count), len(free[lens]))
        for item in free[lens][:need_done]:
            put(item, done_status_for(lens))
        free[lens] = free[lens][need_done:]

    # Gap budget, distributed over the lenses by remaining free counts.
    quotas = _split_budget(
        snapshot.open_gaps - pinned_gaps, {lens: len(free[lens]) for lens in LENSES}
    )
    for lens in LENSES:
        n_gaps = quotas[lens]
        gap_items = free[lens][len(free[lens]) - n_gaps :] if n_gaps else []
        for item in gap_items:
            put(item, gap_status_for(lens), "Major", "No" if lens == "Compliance" else None)
            gap_ids.append(item.id)
            severity[item.id] = "Major"
        for item in free[lens][: len(free[lens]) - n_gaps]:
            put(item, in_progress_status_for(lens))

    _assign_critical(results, severity, gap_ids, applicable, snapshot, preferred_critical_ids)
    return results


def _assign_critical(
    results: dict[str, SynthResult],
    severity: dict[str, str | None],
    gap_ids: list[str],
    applicable: Sequence[SynthItem],
    snapshot: Snapshot,
    preferred: Sequence[str],
) -> None:
    """Mark ``snapshot.critical_gaps`` gap items Critical: preferred first, then lowest gate/id."""
    already = sum(1 for g in gap_ids if severity.get(g) == "Critical")
    need = snapshot.critical_gaps - already
    if need <= 0:
        return
    by_id = {i.id: i for i in applicable}
    gap_set = set(gap_ids)
    ordered = [p for p in preferred if p in gap_set]
    ordered += sorted((g for g in gap_ids if g not in ordered), key=lambda g: _sort_key(by_id[g]))
    for gap_id in ordered:
        if need <= 0:
            break
        if severity.get(gap_id) == "Critical":
            continue
        current = results[gap_id]
        results[gap_id] = SynthResult(current.status, "Critical", current.design_effectiveness)
        severity[gap_id] = "Critical"
        need -= 1
