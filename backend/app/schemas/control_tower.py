"""GET /control-tower (spec §8.2, FR-011). The register, region chart, escalations and calendar use ALL
filters. The KPI tiles ignore the tile filters (status, rag, decision_within_days, has_critical,
compliance_below) and the heatmap ignores portfolio and gate, so the user keeps context while a tile
or heatmap cell is active.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.common import KpiTileOut, PersonRef
from app.schemas.transitions import TransitionFilters, TransitionSummaryOut


class GateRefOut(BaseModel):
    code: str
    short: str
    label: str
    type: str  # stage_review | decision | closure


class HeatmapCellOut(BaseModel):
    portfolio: str
    gate: str  # gate code
    count: int
    worst_rag: str | None  # Red > Amber > Green > Grey; None when count == 0


class HeatmapOut(BaseModel):
    """Portfolio (rows) x gate (columns). All 6 portfolios and all 7 gates are always present."""

    portfolios: list[str]
    gates: list[GateRefOut]
    cells: list[HeatmapCellOut]


class RegionReadinessOut(BaseModel):
    region: str
    average_readiness: (
        int | None
    )  # mean overall readiness of launched transitions (round half up); None if none
    transitions: int


class EscalationOut(BaseModel):
    """Escalation queue row: every Red transition plus any transition with a blocker note."""

    transition_id: str
    transition_name: str
    portfolio: str
    current_gate_short: str
    rag: str
    reason: str  # e.g. "3 critical gaps · AtD decision in 4 days"
    blocker_note: str | None
    owner: PersonRef  # the OR focal
    days_to_next_decision: int | None


class CalendarEntryOut(BaseModel):
    """Decision calendar row (next 45 days of AtD / AtO / Closure decisions)."""

    date: date
    days: int
    transition_id: str
    transition_name: str
    gate: str
    gate_short: str
    decision: str  # "AtD decision" | "AtO decision" | "Closure"
    rag: str
    or_focal: PersonRef


class OperatingRhythmRowOut(BaseModel):
    """Static operating-rhythm card (from the client prototype, spec §8.2)."""

    forum: str
    frequency: str
    input: str
    output: str


class ControlTowerOut(BaseModel):
    today: date
    filters: TransitionFilters  # echo of the applied filters
    kpis: list[KpiTileOut]
    heatmap: HeatmapOut
    readiness_by_region: list[RegionReadinessOut]
    transitions: list[TransitionSummaryOut]  # the transition register (filtered)
    escalations: list[EscalationOut]
    calendar: list[CalendarEntryOut]
    operating_rhythm: list[OperatingRhythmRowOut]
