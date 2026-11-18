"""Creating conditions – shared by item status changes ("Compliant with conditions", BR-030) and gate
reviews / decisions ("Proceed with conditions", "Approve with conditions", BR-040).

A condition lets an open item carry past a gate with an owner and a due gate (spec §4). While it is
open and due AFTER the transition's current gate it covers the item for readiness (BR-020, A-33).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.domain import audit
from app.domain.ids import next_id
from app.errors import BadRequest
from app.models import Condition, Transition, TransitionItem, User
from app.rules.constants import GATE_ORDER, GATE_SHORT

CONDITION_FIELDS = (
    "transition_item_id",
    "set_at_gate",
    "due_gate",
    "owner_user_id",
    "text",
    "status",
)


def create_condition(
    db: Session,
    *,
    transition: Transition,
    item: TransitionItem | None,
    set_at_gate: str,
    due_gate: str,
    owner_user_id: str | None,
    text: str,
    actor: User | None,
    actor_type: str,
    note: str = "",
) -> Condition:
    """Create an OPEN condition + audit event (caller commits). Raises 422 on invalid input.

    Callers enforce their own stricter rules (e.g. gate decisions require the due gate to be LATER
    than the decided gate); here the due gate may not be earlier than the gate it is set at.
    """
    reasons: list[str] = []
    if set_at_gate not in GATE_ORDER:
        reasons.append(f"Unknown gate '{set_at_gate}'")
    if due_gate not in GATE_ORDER:
        reasons.append(f"Unknown due gate '{due_gate}'")
    if not reasons and GATE_ORDER[due_gate] < GATE_ORDER[set_at_gate]:
        reasons.append("A condition cannot be due before the gate it is set at")
    if not text or not text.strip():
        reasons.append("Condition text is required")
    if not owner_user_id:
        reasons.append("Condition owner is required")
    if reasons:
        raise BadRequest("Invalid condition", reasons)

    condition = Condition(
        id=next_id(db, Condition.id, "CON-"),
        transition_id=transition.id,
        transition_item_id=item.id if item is not None else None,
        set_at_gate=set_at_gate,
        due_gate=due_gate,
        owner_user_id=owner_user_id,
        text=text.strip(),
        status="Open",
    )
    db.add(condition)
    db.flush()
    audit.record(
        db,
        actor=actor,
        actor_type=actor_type,
        entity="Condition",
        entity_id=condition.id,
        action="created",
        transition_id=transition.id,
        after=audit.snapshot(condition, CONDITION_FIELDS),
        note=note,
    )
    return condition


def close_superseded_conditions(
    db: Session,
    *,
    transition: Transition,
    item: TransitionItem | None,
    gate: str,
    new_condition: Condition,
    actor: User | None,
    actor_type: str,
) -> list[str]:
    """Re-conditioning (BE#8): when a gate outcome puts a NEW condition on an item that still has an
    open condition due at or before ``gate``, the old one is closed with the note
    "Re-conditioned at <gate> as CON-xxx" so the item never carries two open conditions.
    Audited per closed condition; returns the ids closed. Caller commits."""
    if item is None or gate not in GATE_ORDER:
        return []
    older = db.scalars(
        select(Condition).where(
            Condition.transition_id == transition.id,
            Condition.transition_item_id == item.id,
            Condition.status == "Open",
            Condition.id != new_condition.id,
        )
    ).all()
    closed: list[str] = []
    for old in older:
        if GATE_ORDER.get(old.due_gate, 99) > GATE_ORDER[gate]:
            continue
        before = audit.snapshot(old, CONDITION_FIELDS)
        old.status = "Closed"
        old.close_note = f"Re-conditioned at {GATE_SHORT[gate]} as {new_condition.id}"
        old.closed_by = actor.id if actor is not None else None
        old.closed_at = clock.now()
        audit.record(
            db,
            actor=actor,
            actor_type=actor_type,
            entity="Condition",
            entity_id=old.id,
            action="closed",
            transition_id=transition.id,
            before=before,
            after=audit.snapshot(old, CONDITION_FIELDS),
            note=old.close_note,
        )
        closed.append(old.id)
    return closed
