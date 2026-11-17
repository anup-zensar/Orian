"""RAG status (BR-021, spec §7.4; reference.json -> rag_rule). PURE. Computed live, never stored.

* Red   : critical_gaps >= 2  OR  min lens readiness < 50  OR  (critical_gaps >= 1 AND decision in <= 7 days)
* Amber : critical_gaps >= 1  OR  min lens readiness < 70
* Green : otherwise
* Grey  : the assessment has no items yet (A-34, "not started")
"""

from __future__ import annotations

from collections.abc import Mapping

RED = "Red"
AMBER = "Amber"
GREEN = "Green"
GREY = "Grey"


def compute_rag(
    critical_gaps: int,
    lens_readiness: Mapping[str, int],
    days_to_next_decision: int | None,
    has_items: bool = True,
) -> str:
    if not has_items:
        return GREY
    lowest = min(lens_readiness.values()) if lens_readiness else 100
    near_decision = days_to_next_decision is not None and days_to_next_decision <= 7
    if critical_gaps >= 2 or lowest < 50 or (critical_gaps >= 1 and near_decision):
        return RED
    if critical_gaps >= 1 or lowest < 70:
        return AMBER
    return GREEN
