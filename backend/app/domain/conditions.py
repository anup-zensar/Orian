"""Creating conditions – shared by item status changes ("Compliant with conditions", BR-030) and gate
reviews / decisions ("Proceed with conditions", "Approve with conditions", BR-040).

A condition lets an open item carry past a gate with an owner and a due gate (spec §4). While it is
open and due AFTER the transition's current gate it covers the item for readiness (BR-020, A-33).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain import audit
from app.domain.ids import next_id
from app.errors import BadRequest
from app.models import Condition, Transition, TransitionItem, User
from app.rules.constants import GATE_ORDER

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
