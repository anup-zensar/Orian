"""RAG status (BR-021, spec §7.4; reference.json -> rag_rule). PURE. Computed live, never stored.

* Red   : critical_gaps >= 2  OR  min lens readiness < 50  OR  (critical_gaps >= 1 AND decision in <= 7 days)
* Amber : critical_gaps >= 1  OR  min lens readiness < 70
  (the numbers are the defaults of ``RagThresholds``; the Admin edits them in Rules & thresholds)
* Green : otherwise
* Grey  : the assessment has no items yet (A-34, "not started")
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

RED = "Red"
AMBER = "Amber"
GREEN = "Green"
GREY = "Grey"


@dataclass(frozen=True)
class RagThresholds:
    """The numbers behind Red and Amber (defaults = the client's rule above)."""

    red_critical_gaps: int = 2
    red_lens_below: int = 50
    red_near_days: int = 7
    amber_critical_gaps: int = 1
    amber_lens_below: int = 70


DEFAULT_RAG = RagThresholds()


def compute_rag(
    critical_gaps: int,
    lens_readiness: Mapping[str, int],
    days_to_next_decision: int | None,
    has_items: bool = True,
    thresholds: RagThresholds = DEFAULT_RAG,
) -> str:
    if not has_items:
        return GREY
    lowest = min(lens_readiness.values()) if lens_readiness else 100
    near_decision = (
        days_to_next_decision is not None and days_to_next_decision <= thresholds.red_near_days
    )
    if (
        critical_gaps >= thresholds.red_critical_gaps
        or lowest < thresholds.red_lens_below
        or (critical_gaps >= thresholds.amber_critical_gaps and near_decision)
    ):
        return RED
    if critical_gaps >= thresholds.amber_critical_gaps or lowest < thresholds.amber_lens_below:
        return AMBER
    return GREEN
