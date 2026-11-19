"""Orion insights (FR-010, FR-011): gather deterministic FACTS, let the AI service phrase them.

This module only reads. Insights never write anything (BR-050): their buttons are plain links in M2
(real chasers and proposals arrive with M5 / M8).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app import clock
from app.domain import cfg
from app.domain.dashboard import is_gap, is_open_item, open_actions, pending_approvals
from app.domain.metrics import TransitionMetrics, compute_metrics, decision_phrase
from app.domain.transitions import filter_transitions, my_transitions
from app.errors import NotFound
from app.models import Transition, User
from app.rules.constants import GATE_ORDER, GATE_SHORT
from app.rules.rag import AMBER, RED
from app.schemas.orion import InsightOut, InsightsOut
from app.schemas.transitions import TransitionFilters
from app.services.factory import get_ai_service


def _severity_rank(db: Session) -> dict[str, int]:
    """Position of each severity in the "Gap severities" list (the first one is the most serious)."""
    return {v: i for i, v in enumerate(cfg.option_values(db, "severities", active_only=False))}


def _gap_items(db: Session, m: TransitionMetrics) -> list[dict[str, Any]]:
    """Open gaps at the current gate, most serious first, then by due gate and item id."""
    rank = _severity_rank(db)
    gate = m.transition.current_gate
    gaps = [i for i in m.items if is_gap(i) and is_open_item(i, gate)]
    gaps.sort(
        key=lambda i: (
            rank.get(i.gap_severity or "", len(rank)),
            GATE_ORDER[i.due_gate],
            i.playbook_item_id,
        )
    )
    return [
        {"id": i.playbook_item_id, "title": i.title, "severity": i.gap_severity, "lens": i.lens}
        for i in gaps
    ]


def _transition_facts(db: Session, m: TransitionMetrics) -> dict[str, Any]:
    t = m.transition
    lens, pct = m.lowest_lens()
    return {
        "id": t.id,
        "name": t.name,
        "portfolio": t.portfolio,
        "rag": m.rag,
        "gate_short": GATE_SHORT[t.current_gate],
        "decision_phrase": decision_phrase(m),
        "next_decision_date": t.next_decision_date.isoformat() if t.next_decision_date else None,
        "days": m.days_to_next_decision,
        "launched": m.launched,
        "overall_readiness": m.readiness.overall,
        "critical_gaps": m.critical_gaps,
        "open_gaps": m.open_gaps,
        "lowest_lens": lens,
        "lowest_lens_pct": pct,
        "blocker_note": t.blocker_note,
        "gaps": _gap_items(db, m),
    }


def _urgency(f: dict[str, Any]) -> tuple[bool, int, str]:
    return (f["days"] is None, f["days"] if f["days"] is not None else 0, f["name"].lower())


def dashboard_facts(db: Session, user: User) -> dict[str, Any]:
    mine = my_transitions(db, user)
    facts = [_transition_facts(db, m) for m in mine]
    names = {m.id: m.transition.name for m in mine}
    today = clock.today()
    low_below = cfg.thresholds(db)["insights"]["low_readiness_below"]
    within_days = cfg.thresholds(db)["insights"]["within_days"]

    critical = sorted((f for f in facts if f["critical_gaps"] > 0), key=_urgency)
    low = sorted(
        (
            f
            for f in facts
            if f["launched"]
            and f["lowest_lens_pct"] < low_below
            and f["days"] is not None
            and 0 <= f["days"] <= within_days
        ),
        key=_urgency,
    )
    approvals = [
        {
            "request_id": a.request_id,
            "label": a.label,
            "transition_id": a.transition_id,
            "transition_name": a.transition_name,
            "waiting_days": a.waiting_days,
        }
        for a in pending_approvals(db, user)
    ]
    overdue = []
    for a in open_actions(db, list(names)):
        if a.due_date is not None and a.due_date < today:
            overdue.append(
                {
                    "id": a.id,
                    "title": a.title,
                    "transition_id": a.transition_id,
                    "transition_name": names[a.transition_id],
                    "days_overdue": (today - a.due_date).days,
                }
            )
    overdue.sort(key=lambda a: (-a["days_overdue"], a["id"]))
    return {
        "scope": "dashboard",
        "user": {"id": user.id, "name": user.name, "role": user.role},
        "today": today.isoformat(),
        "transitions": len(facts),
        "critical_transitions": critical,
        "approvals_waiting": approvals,
        "overdue_actions": overdue,
        "low_readiness": low,
    }


def control_tower_facts(db: Session, user: User, filters: TransitionFilters) -> dict[str, Any]:
    rows = filter_transitions(db, user, filters)
    risky = [m for m in rows if m.rag in (RED, AMBER) or m.critical_gaps > 0]
    risky.sort(
        key=lambda m: (
            m.rag != RED,
            -m.critical_gaps,
            m.days_to_next_decision is None,
            m.days_to_next_decision or 0,
            m.transition.name.lower(),
        )
    )
    return {
        "scope": "control-tower",
        "user": {"id": user.id, "name": user.name, "role": user.role},
        "today": clock.today().isoformat(),
        "transitions": len(rows),
        "red": sum(1 for m in rows if m.rag == RED),
        "top_risks": [
            _transition_facts(db, m) for m in risky[: cfg.thresholds(db)["narrative_top"]]
        ],
    }


def transition_facts(db: Session, user: User, transition_id: str) -> dict[str, Any]:
    t = db.get(Transition, transition_id)
    if t is None:
        raise NotFound(f"Transition {transition_id} not found")
    (m,) = compute_metrics(db, [t])
    return {
        "scope": "transition",
        "user": {"id": user.id, "name": user.name, "role": user.role},
        "today": clock.today().isoformat(),
        "transition": _transition_facts(db, m),
        "has_items": bool(m.items),
    }


def build_insights(
    db: Session,
    user: User,
    scope: str,
    scope_id: str | None,
    filters: TransitionFilters | None = None,
) -> InsightsOut:
    """Facts -> ``AIService.insights`` -> typed response. Read-only (BR-050)."""
    if scope == "dashboard":
        facts = dashboard_facts(db, user)
    elif scope == "control-tower":
        facts = control_tower_facts(db, user, filters or TransitionFilters())
    else:
        if not scope_id:
            raise NotFound("Transition id is required for scope=transition")
        facts = transition_facts(db, user, scope_id)
    cards = get_ai_service().insights(facts)
    return InsightsOut(
        scope=scope,
        scope_id=scope_id if scope == "transition" else None,
        generated_by="Orion agent",
        insights=[InsightOut.model_validate(c) for c in cards],
    )
