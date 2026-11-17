"""Control tower aggregates (FR-011, spec §8.2).

The register, region chart, escalations and calendar use ALL filters. To keep the user's context the
KPI tiles ignore the tile filters (:data:`TILE_FILTER_KEYS`) and the heatmap ignores portfolio and
gate (:data:`HEATMAP_FILTER_KEYS`): the tiles still show the whole picture while one is active, and
the heatmap still shows every cell while one is selected. Metrics are computed once per request.
"""

from __future__ import annotations

from fractions import Fraction

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.domain.metrics import (
    TransitionMetrics,
    compute_metrics,
    decision_phrase,
    plural,
    reference_lists,
    to_summary,
)
from app.domain.transitions import filter_metrics
from app.models import Transition, User
from app.rules.constants import GATE_SHORT
from app.rules.rag import AMBER, GREEN, GREY, RED
from app.rules.readiness import round_half_up
from app.schemas.common import KpiTileOut
from app.schemas.control_tower import (
    CalendarEntryOut,
    ControlTowerOut,
    EscalationOut,
    GateRefOut,
    HeatmapCellOut,
    HeatmapOut,
    OperatingRhythmRowOut,
    RegionReadinessOut,
)
from app.schemas.transitions import TransitionFilters

CALENDAR_GATES = {"SG4_ATD": "AtD decision", "SG6_ATO": "AtO decision", "CLOSURE": "Closure"}
CALENDAR_HORIZON_DAYS = 45
_RAG_SEVERITY = {RED: 3, AMBER: 2, GREEN: 1, GREY: 0}

TILE_FILTER_KEYS = ("status", "rag", "decision_within_days", "has_critical", "compliance_below")
HEATMAP_FILTER_KEYS = ("portfolio", "gate")

OPERATING_RHYTHM = [
    ("OR team stand-up", "Weekly", "Red/amber transitions, overdue deliverables", "Owners and dates for blockers"),
    (
        "Portfolio / regional SME review",
        "Fortnightly",
        'Portfolio heatmap, "to confirm" applicability',
        "Golden-set updates, confirmed scope",
    ),
    (
        "IRM checkpoint",
        "Before each gate",
        "Open compliance controls, exceptions",
        "IRM attestation or exception",
    ),
    (
        "Leadership update",
        "Monthly",
        "LT brief, escalations, decisions due",
        "Decisions, support, risk acceptance",
    ),
]  # fmt: skip


def worst_rag(rags: list[str]) -> str | None:
    """Red > Amber > Green > Grey; None for an empty list."""
    return max(rags, key=lambda r: _RAG_SEVERITY[r]) if rags else None


def build_kpis(rows: list[TransitionMetrics]) -> list[KpiTileOut]:
    """The five tiles; each ``filter`` reproduces the tile's count in the register (FR-011)."""
    return [
        KpiTileOut(
            key="active",
            label="Active transitions",
            value=sum(1 for m in rows if m.transition.status == "Active"),
            tone="neutral",
            hint="Transitions that are not closed",
            filter={"status": "Active"},
        ),
        KpiTileOut(
            key="red",
            label="Red",
            value=sum(1 for m in rows if m.rag == RED),
            tone="danger",
            hint="Two or more critical gaps, a lens below 50%, or a critical gap within 7 days of a decision",
            filter={"rag": "Red"},
        ),
        KpiTileOut(
            key="decisions_14d",
            label="Decisions ≤ 14 days",
            value=sum(
                1
                for m in rows
                if m.days_to_next_decision is not None and m.days_to_next_decision <= 14
            ),
            tone="warning",
            hint="Next gate decision due within 14 days (overdue included)",
            filter={"decision_within_days": "14"},
        ),
        KpiTileOut(
            key="critical",
            label="With critical gaps",
            value=sum(1 for m in rows if m.critical_gaps > 0),
            tone="danger",
            hint="At least one open critical gap",
            filter={"has_critical": "true"},
        ),
        KpiTileOut(
            key="compliance_below_70",
            label="Compliance readiness < 70%",
            value=sum(1 for m in rows if m.launched and m.lens_pct["Compliance"] < 70),
            tone="warning",
            hint="Compliance lens readiness below 70% at the current gate",
            filter={"compliance_below": "70"},
        ),
    ]


def build_heatmap(rows: list[TransitionMetrics], ref: dict) -> HeatmapOut:
    gates = [
        GateRefOut(code=g["code"], short=g["short"], label=g["label"], type=g["type"])
        for g in ref["gates"]
    ]
    cells = []
    for portfolio in ref["portfolios"]:
        for gate in gates:
            rags = [
                m.rag
                for m in rows
                if m.transition.portfolio == portfolio and m.transition.current_gate == gate.code
            ]
            cells.append(
                HeatmapCellOut(
                    portfolio=portfolio, gate=gate.code, count=len(rags), worst_rag=worst_rag(rags)
                )
            )
    return HeatmapOut(portfolios=list(ref["portfolios"]), gates=gates, cells=cells)


def build_regions(rows: list[TransitionMetrics], ref: dict) -> list[RegionReadinessOut]:
    out = []
    for region in ref["regions"]:
        in_region = [m for m in rows if m.transition.region == region]
        scores = [m.readiness.overall for m in in_region if m.launched]  # A-34: not launched
        out.append(
            RegionReadinessOut(
                region=region,
                average_readiness=(
                    round_half_up(Fraction(sum(scores), len(scores))) if scores else None
                ),
                transitions=len(in_region),
            )
        )
    return out


def escalation_reason(m: TransitionMetrics) -> str:
    """e.g. ``3 critical gaps · AtD decision in 4 days`` or ``Compliance readiness 45%``."""
    parts: list[str] = []
    lens, pct = m.lowest_lens()
    if m.critical_gaps > 0:
        parts.append(plural(m.critical_gaps, "critical gap"))
    if not m.launched:
        parts.append("Assessment not launched")
    elif pct < 70:
        parts.append(f"{lens} readiness {pct}%")
    decision = decision_phrase(m)
    if decision:
        parts.append(decision)
    if not parts:
        parts.append("Blocker noted")
    return " · ".join(parts)


def build_escalations(rows: list[TransitionMetrics]) -> list[EscalationOut]:
    """Every Red transition plus every transition with a blocker note; Red first, then days ascending."""
    chosen = [m for m in rows if m.rag == RED or (m.transition.blocker_note or "").strip()]
    chosen.sort(
        key=lambda m: (
            m.rag != RED,
            m.days_to_next_decision is None,
            m.days_to_next_decision or 0,
            m.transition.name.lower(),
        )
    )
    return [
        EscalationOut(
            transition_id=m.id,
            transition_name=m.transition.name,
            portfolio=m.transition.portfolio,
            current_gate_short=GATE_SHORT[m.transition.current_gate],
            rag=m.rag,
            reason=escalation_reason(m),
            blocker_note=m.transition.blocker_note,
            owner=m.or_focal,
            days_to_next_decision=m.days_to_next_decision,
        )
        for m in chosen
    ]


def build_calendar(rows: list[TransitionMetrics]) -> list[CalendarEntryOut]:
    """AtD / AtO / Closure decisions at most 45 days ahead (overdue ones first), sorted by date."""
    entries = []
    for m in rows:
        t = m.transition
        days = m.days_to_next_decision
        if t.current_gate not in CALENDAR_GATES or t.next_decision_date is None or days is None:
            continue
        if days > CALENDAR_HORIZON_DAYS:
            continue
        entries.append(
            CalendarEntryOut(
                date=t.next_decision_date,
                days=days,
                transition_id=t.id,
                transition_name=t.name,
                gate=t.current_gate,
                gate_short=GATE_SHORT[t.current_gate],
                decision=CALENDAR_GATES[t.current_gate],
                rag=m.rag,
                or_focal=m.or_focal,
            )
        )
    entries.sort(key=lambda e: (e.date, e.transition_name.lower()))
    return entries


def build_control_tower(db: Session, user: User, filters: TransitionFilters) -> ControlTowerOut:
    everything = compute_metrics(db, list(db.scalars(select(Transition)).all()))
    rows = filter_metrics(everything, user, filters)
    tile_filters = filters.model_copy(update={k: None for k in TILE_FILTER_KEYS})
    heat_filters = filters.model_copy(update={k: None for k in HEATMAP_FILTER_KEYS})
    ref = reference_lists(db)
    return ControlTowerOut(
        today=clock.today(),
        filters=filters,
        kpis=build_kpis(filter_metrics(everything, user, tile_filters)),
        heatmap=build_heatmap(filter_metrics(everything, user, heat_filters), ref),
        readiness_by_region=build_regions(rows, ref),
        transitions=[to_summary(m) for m in rows],
        escalations=build_escalations(rows),
        calendar=build_calendar(rows),
        operating_rhythm=[
            OperatingRhythmRowOut(forum=a, frequency=b, input=c, output=d)
            for a, b, c, d in OPERATING_RHYTHM
        ],
    )
