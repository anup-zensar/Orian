"""Shared bulk metrics for every M2 endpoint (BR-020, BR-021, FR-012; A-09, A-33, A-34).

One function, :func:`compute_metrics`, loads the checklist rows of many transitions in a single query
(plus the open conditions and approved exceptions that "cover" items) and derives readiness, days to
the next decision and RAG with the pure rules in ``app.rules``. The register, control tower,
dashboard and insights all call it, so they can never disagree. Nothing computed here is stored.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.models import (
    Condition,
    ExceptionRecord,
    PlaybookItem,
    ReferenceData,
    Transition,
    TransitionItem,
    User,
)
from app.rules.constants import GATE_ORDER, GATE_SHORT, GATE_TYPE
from app.rules.rag import compute_rag
from app.rules.readiness import Readiness, ReadinessItem, compute_readiness
from app.schemas.common import LensValues, PersonRef
from app.schemas.transitions import TransitionSummaryOut


@dataclass(frozen=True)
class ItemRow:
    """One checklist line with the playbook fields the M2 views need."""

    id: int  # TransitionItem.id
    playbook_item_id: str
    title: str
    lens: str
    applicability: str
    status: str
    gap_severity: str | None
    owner_user_id: str | None
    due_gate: str
    note: str
    covered: bool  # open condition due after the gate, or approved exception (A-09, A-33)


@dataclass
class TransitionMetrics:
    """A transition plus everything computed from its checklist."""

    transition: Transition
    items: list[ItemRow]
    readiness: Readiness
    days_to_next_decision: int | None
    rag: str
    or_focal: PersonRef = field(default_factory=lambda: PersonRef(id="", name=""))

    @property
    def id(self) -> str:
        return self.transition.id

    @property
    def launched(self) -> bool:
        """False while the assessment has no checklist items (A-34): no readiness to speak of."""
        return bool(self.items)

    @property
    def critical_gaps(self) -> int:
        return self.readiness.critical_gaps

    @property
    def open_gaps(self) -> int:
        return self.readiness.open_gaps

    @property
    def lens_pct(self) -> dict[str, int]:
        return self.readiness.lens_pct

    def lowest_lens(self) -> tuple[str, int]:
        """(lens, %) with the lowest readiness; ties resolve in lens order Business, Technical, ..."""
        pct = self.lens_pct
        lens = min(pct, key=lambda name: pct[name])
        return lens, pct[lens]


def days_until(transition: Transition) -> int | None:
    """Days from the demo "today" to the next decision date (negative when past), or None."""
    if transition.next_decision_date is None:
        return None
    return (transition.next_decision_date - clock.today()).days


def compute_metrics(db: Session, transitions: Sequence[Transition]) -> list[TransitionMetrics]:
    """Metrics for ``transitions`` in the same order, using a handful of queries in total."""
    if not transitions:
        return []
    ids = [t.id for t in transitions]

    # Items joined to the playbook lens/title (one query, plain columns for speed).
    rows = db.execute(
        select(
            TransitionItem.id,
            TransitionItem.transition_id,
            TransitionItem.playbook_item_id,
            TransitionItem.applicability,
            TransitionItem.status,
            TransitionItem.gap_severity,
            TransitionItem.owner_user_id,
            TransitionItem.due_gate,
            TransitionItem.note,
            PlaybookItem.lens,
            PlaybookItem.title,
        )
        .join(PlaybookItem, PlaybookItem.id == TransitionItem.playbook_item_id)
        .where(TransitionItem.transition_id.in_(ids))
        .order_by(TransitionItem.transition_id, TransitionItem.id)
    ).all()

    # Open conditions: item -> highest due gate order. Approved exceptions: set of item ids.
    cond_due: dict[int, int] = {}
    for item_id, due_gate in db.execute(
        select(Condition.transition_item_id, Condition.due_gate).where(
            Condition.status == "Open",
            Condition.transition_item_id.is_not(None),
            Condition.transition_id.in_(ids),
        )
    ).all():
        cond_due[item_id] = max(cond_due.get(item_id, -1), GATE_ORDER.get(due_gate, -1))
    excepted = set(
        db.scalars(
            select(ExceptionRecord.transition_item_id).where(
                ExceptionRecord.status == "Approved",
                ExceptionRecord.transition_item_id.is_not(None),
                ExceptionRecord.transition_id.in_(ids),
            )
        ).all()
    )

    by_transition: dict[str, list[Any]] = {tid: [] for tid in ids}
    for row in rows:
        by_transition[row.transition_id].append(row)

    users = {u.id: u for u in db.scalars(select(User)).all()}
    result: list[TransitionMetrics] = []
    for t in transitions:
        gate_order = GATE_ORDER[t.current_gate]
        item_rows = [
            ItemRow(
                id=r.id,
                playbook_item_id=r.playbook_item_id,
                title=r.title,
                lens=r.lens,
                applicability=r.applicability,
                status=r.status,
                gap_severity=r.gap_severity,
                owner_user_id=r.owner_user_id,
                due_gate=r.due_gate,
                note=r.note or "",
                covered=cond_due.get(r.id, -1) > gate_order or r.id in excepted,
            )
            for r in by_transition[t.id]
        ]
        readiness = compute_readiness(
            [
                ReadinessItem(
                    lens=i.lens,
                    due_gate=i.due_gate,
                    applicability=i.applicability,
                    status=i.status,
                    gap_severity=i.gap_severity,
                    covered=i.covered,
                )
                for i in item_rows
            ],
            t.current_gate,
        )
        if not item_rows:
            # A-34: not launched -> nothing is ready yet (0 %, never the vacuous 100 %).
            readiness = replace(
                readiness,
                lenses={
                    lens: replace(lr, readiness_pct=0) for lens, lr in readiness.lenses.items()
                },
                overall=0,
            )
        days = days_until(t)
        rag = compute_rag(
            readiness.critical_gaps, readiness.lens_pct, days, has_items=bool(item_rows)
        )
        focal = users.get(t.or_focal_user_id)
        result.append(
            TransitionMetrics(
                transition=t,
                items=item_rows,
                readiness=readiness,
                days_to_next_decision=days,
                rag=rag,
                or_focal=PersonRef(id=t.or_focal_user_id, name=focal.name if focal else ""),
            )
        )
    return result


def to_summary(m: TransitionMetrics) -> TransitionSummaryOut:
    """The register row for one transition (FR-012)."""
    t = m.transition
    pct = m.lens_pct
    return TransitionSummaryOut(
        id=t.id,
        name=t.name,
        portfolio=t.portfolio,
        region=t.region,
        market=t.market,
        project_type=t.project_type,
        current_gate=t.current_gate,
        current_gate_short=GATE_SHORT[t.current_gate],
        current_gate_type=GATE_TYPE[t.current_gate],
        risk_tier=t.risk_tier,
        tier_status=t.tier_status,
        status=t.status,
        is_flagship=t.is_flagship,
        autonomous_mode=t.autonomous_mode,
        assessment_launched=t.assessment_launched_at is not None,
        or_focal=m.or_focal,
        next_decision_date=t.next_decision_date,
        days_to_next_decision=m.days_to_next_decision,
        lens_readiness=LensValues(
            Business=pct["Business"], Technical=pct["Technical"], Compliance=pct["Compliance"]
        ),
        overall_readiness=m.readiness.overall,
        open_gaps=m.open_gaps,
        critical_gaps=m.critical_gaps,
        rag=m.rag,
        blocker_note=t.blocker_note,
    )


def reference_lists(db: Session) -> dict[str, Any]:
    """Ordered portfolios, regions and gate descriptors from reference data (reference order)."""
    row = db.get(ReferenceData, "reference")
    ref: dict[str, Any] = row.data if row is not None else {}
    return {
        "portfolios": list(ref.get("portfolios", [])),
        "regions": list(ref.get("regions", [])),
        "gates": list(ref.get("gates", [])),
    }


def plural(n: int, word: str) -> str:
    """``1 day`` / ``2 days``."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def decision_phrase(m: TransitionMetrics) -> str | None:
    """``AtD decision in 4 days`` / ``AtD decision overdue by 2 days`` (None without a date)."""
    days = m.days_to_next_decision
    if days is None:
        return None
    gate = m.transition.current_gate
    suffix = {"stage_review": " review", "decision": " decision", "closure": ""}[GATE_TYPE[gate]]
    label = f"{GATE_SHORT[gate]}{suffix}"
    if days < 0:
        return f"{label} overdue by {plural(-days, 'day')}"
    if days == 0:
        return f"{label} today"
    return f"{label} in {plural(days, 'day')}"
