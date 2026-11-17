"""Gate write actions: stage reviews, decisions, request approval (BR-040, BR-041).

Routers stay thin: they call these functions and commit. Every write is audited with actor type Human.
The rules (``app.rules.gates``) decide what is allowed; the readiness check uses the same context
loader, so what the UI shows enabled is what the API accepts.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.domain import audit
from app.domain.conditions import create_condition
from app.domain.readiness_check import latest_chain, load_gate_inputs
from app.errors import BadRequest, Conflict
from app.models import ApprovalRequest, GateReview, OrionDraft, Transition, User
from app.rules import gates as rules
from app.rules.constants import (
    ACTOR_HUMAN,
    GATE_ORDER,
    GATE_SHORT,
    GATE_TYPE,
    GATES,
)
from app.schemas.gates import ConditionIn

REVIEW_FIELDS = ("gate", "gate_type", "outcome", "note", "conditions_created")
DECISION_CHAIN_TYPE = {"SG4_ATD": "AtD", "SG6_ATO": "AtO"}


def next_gate(gate: str) -> str:
    """The gate after ``gate`` (CLOSURE has none and stays CLOSURE)."""
    idx = GATE_ORDER[gate]
    return GATES[idx + 1] if idx + 1 < len(GATES) else gate


def check_condition_shape(db: Session, gate: str, conditions: list[ConditionIn]) -> None:
    """422 for unknown due gate / not later than the gate / missing owner or text / unknown owner."""
    reasons: list[str] = []
    for c in conditions:
        if c.due_gate not in GATE_ORDER:
            reasons.append(f"Condition for {c.item_id}: unknown due gate '{c.due_gate}'")
        elif GATE_ORDER[c.due_gate] <= GATE_ORDER[gate]:
            reasons.append(f"Condition for {c.item_id}: due gate must be after {GATE_SHORT[gate]}")
        if not c.owner_user_id:
            reasons.append(f"Condition for {c.item_id} needs an owner")
        elif db.get(User, c.owner_user_id) is None:
            reasons.append(f"Condition for {c.item_id}: unknown owner '{c.owner_user_id}'")
        if not c.text.strip():
            reasons.append(f"Condition for {c.item_id} needs a text")
    if reasons:
        raise BadRequest("Invalid condition", list(dict.fromkeys(reasons)))


def _to_inputs(conditions: list[ConditionIn]) -> list[rules.ConditionInput]:
    return [
        rules.ConditionInput(c.item_id, c.owner_user_id, c.due_gate, c.text) for c in conditions
    ]


def _create_conditions(
    db: Session,
    transition: Transition,
    gate: str,
    user: User,
    conditions: list[ConditionIn],
    inputs_items: dict,
) -> list[str]:
    created: list[str] = []
    for c in conditions:
        item = inputs_items.get(c.item_id)
        cond = create_condition(
            db,
            transition=transition,
            item=item,
            set_at_gate=gate,
            due_gate=c.due_gate,
            owner_user_id=c.owner_user_id,
            text=c.text,
            actor=user,
            actor_type=ACTOR_HUMAN,
            note=f"Set at {GATE_SHORT[gate]} for {c.item_id}",
        )
        created.append(cond.id)
    return created


def _record_review(
    db: Session,
    transition: Transition,
    gate: str,
    outcome: str,
    user: User,
    note: str,
    created: list[str],
    approval_request_id: str | None = None,
) -> GateReview:
    review = GateReview(
        transition_id=transition.id,
        gate=gate,
        gate_type=GATE_TYPE[gate],
        outcome=outcome,
        decided_by=user.id,
        decided_at=clock.now(),
        note=note,
        conditions_created=created,
        approval_request_id=approval_request_id,
    )
    db.add(review)
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="GateReview",
        entity_id=review.id,
        action="recorded",
        transition_id=transition.id,
        after=audit.snapshot(review, REVIEW_FIELDS),
        note=f"{GATE_SHORT[gate]}: {outcome}" + (f" - {note}" if note else ""),
    )
    return review


def _advance(db: Session, transition: Transition, user: User, new_gate: str, why: str) -> None:
    before = transition.current_gate
    if new_gate == before:
        return
    transition.current_gate = new_gate
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=transition.id,
        action="gate_advanced",
        transition_id=transition.id,
        before={"current_gate": before},
        after={"current_gate": new_gate},
        note=why,
    )


def _check_active(transition: Transition, gate: str) -> None:
    if transition.status == "Closed":
        raise Conflict("Transition is closed", ["The transition is closed"])
    if gate != transition.current_gate:
        raise Conflict(
            f"{GATE_SHORT[gate]} is not the current gate",
            [
                f"{GATE_SHORT[gate]} is not the current gate "
                f"(current: {GATE_SHORT[transition.current_gate]})"
            ],
        )


def record_stage_review(
    db: Session,
    *,
    transition: Transition,
    gate: str,
    outcome: str,
    note: str,
    conditions: list[ConditionIn],
    user: User,
) -> tuple[GateReview, list[str], str]:
    """Record Proceed / Proceed with conditions / Hold. Returns (review, condition ids, new gate).
    Caller commits."""
    if GATE_TYPE[gate] != "stage_review":
        raise Conflict(
            f"{GATE_SHORT[gate]} is not a stage-review gate",
            [f"{GATE_SHORT[gate]} is a decision or closure gate - use the decision"],
        )
    _check_active(transition, gate)
    if outcome not in ("Proceed", "Proceed with conditions", "Hold"):
        raise BadRequest("Unknown outcome", [f"Unknown outcome '{outcome}'"])
    if outcome == "Hold" and not note.strip():
        raise BadRequest("A note is required for Hold", ["A note is required for Hold"])
    check_condition_shape(db, gate, conditions)

    inputs = load_gate_inputs(db, transition, gate)
    result = rules.validate_stage_review(inputs.ctx, outcome, _to_inputs(conditions))
    if not result.allowed:
        raise Conflict(f"{outcome} is not allowed at {GATE_SHORT[gate]}", result.reasons)

    created = _create_conditions(db, transition, gate, user, conditions, inputs.items)
    review = _record_review(db, transition, gate, outcome, user, note, created)
    new_gate = gate
    if outcome != "Hold":
        new_gate = next_gate(gate)
        _advance(db, transition, user, new_gate, f"{outcome} at {GATE_SHORT[gate]}")
    return review, created, new_gate


def _cancel_chain(db: Session, chain: ApprovalRequest, user: User, note: str) -> None:
    from app.domain import approvals

    if chain.status == "Pending":
        approvals.cancel_request(db, request=chain, user=user, note=note)
    elif chain.status == "Approved":
        # An approved chain must not block a fresh request after a Return.
        before = {"status": chain.status}
        chain.status = "Cancelled"
        audit.record(
            db,
            actor=user,
            actor_type=ACTOR_HUMAN,
            entity="ApprovalRequest",
            entity_id=chain.id,
            action="cancelled",
            transition_id=chain.transition_id,
            before=before,
            after={"status": "Cancelled"},
            note=note,
        )


def record_decision(
    db: Session,
    *,
    transition: Transition,
    gate: str,
    decision: str,
    note: str,
    conditions: list[ConditionIn],
    user: User,
) -> tuple[GateReview, list[str], str, bool]:
    """Record Approve / Approve with conditions / Return / Close. Returns (review, condition ids,
    new gate, transition closed). Caller commits."""
    if GATE_TYPE[gate] == "stage_review":
        raise Conflict(
            f"{GATE_SHORT[gate]} is not a decision gate",
            [f"{GATE_SHORT[gate]} is a stage review - record a stage review"],
        )
    _check_active(transition, gate)
    allowed = (
        ("Close", "Return")
        if GATE_TYPE[gate] == "closure"
        else (
            "Approve",
            "Approve with conditions",
            "Return",
        )
    )
    if decision not in allowed:
        raise BadRequest(
            "Unknown decision", [f"Unknown decision '{decision}' for {GATE_SHORT[gate]}"]
        )
    if decision == "Return" and not note.strip():
        raise BadRequest("A note is required for Return", ["A note is required for Return"])
    check_condition_shape(db, gate, conditions)

    inputs = load_gate_inputs(db, transition, gate)
    result = rules.validate_decision(inputs.ctx, decision, _to_inputs(conditions))
    if not result.allowed:
        raise Conflict(f"{decision} is not allowed at {GATE_SHORT[gate]}", result.reasons)

    chain = inputs.chain
    created: list[str] = []
    if decision == "Return":
        if chain is not None:
            _cancel_chain(db, chain, user, f"Returned: {note}")
    else:
        created = _create_conditions(db, transition, gate, user, conditions, inputs.items)
    review = _record_review(
        db, transition, gate, decision, user, note, created, chain.id if chain else None
    )
    new_gate = gate
    closed = False
    if decision in ("Approve", "Approve with conditions"):
        new_gate = next_gate(gate)
        _advance(db, transition, user, new_gate, f"{decision} at {GATE_SHORT[gate]}")
    elif decision == "Close":
        before = {"status": transition.status}
        transition.status = "Closed"
        closed = True
        audit.record(
            db,
            actor=user,
            actor_type=ACTOR_HUMAN,
            entity="Transition",
            entity_id=transition.id,
            action="closed",
            transition_id=transition.id,
            before=before,
            after={"status": "Closed"},
            note="Transition closed",
        )
    return review, created, new_gate, closed


def request_gate_approval(
    db: Session,
    *,
    transition: Transition,
    gate: str,
    user: User,
    note: str = "",
    via_draft_id: int | None = None,
) -> ApprovalRequest:
    """Create the AtD (OLM -> IRM) or AtO (IRM -> OLM) approval chain for a decision gate.

    Validates (409 with reasons): gate is a decision gate, gate == current gate of the transition, no
    Pending/Approved chain already exists for the gate, readiness verdict is Ready or Ready with
    conditions (via the readiness check / rules.gates.evaluate_verdict). Then calls
    ``app.domain.approvals.create_approval_request`` (import it INSIDE this function to avoid import
    cycles) with type "AtD"/"AtO", gate, a subject_label summarising the verdict, created_by=user and
    created_source "Human"; marks the draft ``via_draft_id`` as Sent when given (the router has already
    checked Perm.SEND_DRAFTS). Writes the audit event; caller commits."""
    from app.domain import approvals

    chain_type = DECISION_CHAIN_TYPE.get(gate)
    if chain_type is None:
        raise Conflict(
            f"{GATE_SHORT[gate]} does not need an approval request",
            ["Only the AtD and AtO gates have an approval chain"],
        )
    _check_active(transition, gate)
    existing = latest_chain(db, transition.id, gate)
    if existing is not None and existing.status in ("Pending", "Approved"):
        raise Conflict(
            "An approval request already exists",
            [f"Approval request {existing.id} is already {existing.status.lower()} for this gate"],
        )
    inputs = load_gate_inputs(db, transition, gate)
    result = rules.evaluate_verdict(inputs.ctx)
    if result.verdict == rules.VERDICT_NOT_READY:
        reasons = [f"{b.item_id}: {b.reason}" for b in result.blocking]
        reasons += result.hard_reasons
        raise Conflict(
            f"Not ready for {GATE_SHORT[gate]}", reasons or ["Readiness verdict: Not ready"]
        )

    draft: OrionDraft | None = None
    if via_draft_id is not None:
        draft = db.get(OrionDraft, via_draft_id)

    request = approvals.create_approval_request(
        db,
        type=chain_type,
        transition=transition,
        created_by=user,
        created_source=ACTOR_HUMAN,
        gate=gate,
        subject_label=f"{chain_type} readiness: {result.verdict}",
    )
    if draft is not None and draft.status == "Draft":
        draft.status = "Sent"
        draft.sent_by = user.id
        draft.sent_at = clock.now()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=transition.id,
        action="approval_requested",
        transition_id=transition.id,
        after={"gate": gate, "request_id": request.id, "verdict": result.verdict},
        note=note or f"{chain_type} approval requested ({request.id})",
    )
    return request


def latest_reviews(db: Session, transition_id: str) -> list[GateReview]:
    """All reviews of a transition, chronological."""
    return list(
        db.scalars(
            select(GateReview)
            .where(GateReview.transition_id == transition_id)
            .order_by(GateReview.decided_at, GateReview.id)
        ).all()
    )
