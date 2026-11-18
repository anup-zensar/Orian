"""Gates: readiness check, stage reviews, request approval, decisions (FR-034, FR-050, BR-040). M5."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.domain import gate_actions
from app.domain.readiness_check import (
    approval_out,
    compute_readiness_check,
    latest_chain,
    load_gate_inputs,
    person,
)
from app.errors import BadRequest, NotFound
from app.models import GateReview, OrionDraft, Transition, User
from app.permissions import Perm
from app.rules import gates as rules
from app.rules.constants import DONE_STATUSES, GATE_ORDER, GATE_SHORT, GATE_TYPE, GATES
from app.schemas.common import ErrorOut
from app.schemas.gates import (
    GateApprovalRequestIn,
    GateApprovalRequestOut,
    GateDecisionIn,
    GateOverview,
    GateReviewIn,
    GateReviewOut,
    GateReviewRecord,
    GatesOverviewOut,
    ReadinessCheckOut,
)

router = APIRouter(tags=["gates"], dependencies=[Depends(get_current_user)])

_ERR = {403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}}


def _transition(db: Session, transition_id: str) -> Transition:
    transition = db.get(Transition, transition_id)
    if transition is None:
        raise NotFound(f"Transition {transition_id} not found")
    return transition


def _valid_gate(gate: str) -> str:
    if gate not in GATE_ORDER:
        raise BadRequest(
            "Unknown gate", [f"Unknown gate '{gate}' (expected one of {', '.join(GATES)})"]
        )
    return gate


def _record(db: Session, review: GateReview) -> GateReviewRecord:
    users = {u.id: u for u in db.query(User).all()}
    return GateReviewRecord(
        id=review.id,
        gate=review.gate,
        gate_type=review.gate_type,
        outcome=review.outcome,
        decided_by=person(users, review.decided_by),
        decided_at=review.decided_at,
        note=review.note or "",
        conditions_created=list(review.conditions_created or []),
    )


@router.get(
    "/transitions/{transition_id}/readiness",
    response_model=ReadinessCheckOut,
    responses={404: {"model": ErrorOut}, 422: {"model": ErrorOut}},
)
def get_readiness(
    transition_id: str,
    gate: str | None = Query(default=None, description="Gate code; default = current gate"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReadinessCheckOut:
    """Readiness check (FR-050, spec 8.9) for ``gate`` (default: the transition's current gate).

    Read-only; any signed-in user. 404 unknown transition; 422 unknown gate code. Delegates to
    ``domain.readiness_check.compute_readiness_check``. Rules produce verdict, blockers and decision
    option states; the narrative and recommended actions are labelled "Orion agent"."""
    transition = _transition(db, transition_id)
    code = _valid_gate(gate) if gate else transition.current_gate
    return compute_readiness_check(db, transition, code, user)


@router.get(
    "/transitions/{transition_id}/gates",
    response_model=GatesOverviewOut,
    responses={404: {"model": ErrorOut}},
)
def get_gates_overview(
    transition_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GatesOverviewOut:
    """Gate history for the Gates & decisions tab (spec 8.7e): all 7 gates in order with state
    (before current = done, current, later = upcoming; a Closed transition has all done), the
    GateReview records per gate (outcome, decider, time, note, conditions created), the number of carried
    items per gate and, for decision gates, the latest approval chain (steps, approver, status)."""
    from app.domain.metrics import reference_lists

    transition = _transition(db, transition_id)
    labels = {g["code"]: g.get("label", "") for g in reference_lists(db)["gates"]}
    reviews: dict[str, list[GateReviewRecord]] = {g: [] for g in GATES}
    for r in gate_actions.latest_reviews(db, transition.id):
        if r.gate in reviews:
            reviews[r.gate].append(_record(db, r))

    inputs = load_gate_inputs(db, transition, transition.current_gate)
    facts = [
        rules.ConditionFact(
            id=c.id,
            item_id=next(
                (pid for pid, row in inputs.items.items() if row.id == c.transition_item_id), None
            ),
            set_at_gate=c.set_at_gate,
            due_gate=c.due_gate,
            owner_user_id=c.owner_user_id,
            text=c.text,
            status=c.status,
        )
        for c in inputs.conditions
    ]
    done = {pid: row.status in DONE_STATUSES for pid, row in inputs.items.items()}
    closed = transition.status == "Closed"
    current = GATE_ORDER[transition.current_gate]
    gates: list[GateOverview] = []
    for code in GATES:
        order = GATE_ORDER[code]
        state = (
            "done" if closed or order < current else ("current" if order == current else "upcoming")
        )
        gates.append(
            GateOverview(
                code=code,
                short=GATE_SHORT[code],
                label=labels.get(code) or GATE_SHORT[code],
                type=GATE_TYPE[code],
                state=state,  # type: ignore[arg-type]
                reviews=reviews[code],
                carried_items=len(rules.carried_items(facts, done, code)),
                approval=(
                    approval_out(latest_chain(db, transition.id, code), inputs.users)
                    if GATE_TYPE[code] == "decision"
                    else None
                ),
            )
        )
    return GatesOverviewOut(current_gate=transition.current_gate, gates=gates)


@router.post(
    "/transitions/{transition_id}/gates/{gate}/review",
    response_model=GateReviewOut,
    responses=_ERR,
)
def record_stage_review(
    transition_id: str,
    gate: str,
    body: GateReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.RECORD_STAGE_REVIEW)),
) -> GateReviewOut:
    """Record a stage review (BR-040): Proceed / Proceed with conditions / Hold.

    403 unless the transition's OR focal (Perm.RECORD_STAGE_REVIEW). 404 unknown transition. 409 (reasons[]) when: the gate
    is not a stage-review gate (SG0, SG2, SG3, SG5_HYPERCARE), gate != the transition's current gate,
    the transition is Closed, or ``rules.gates.validate_stage_review`` disallows the outcome (open
    uncovered items, missing conditions, unconfirmed tier at SG0, Compliance rule, SG3 rule A-12).
    422 for unknown outcome, Hold without note, condition with unknown due gate / not later than the gate /
    missing owner or text. On success: creates the GateReview, creates one Condition per ``conditions``
    entry via ``domain.conditions.create_condition`` (set_at_gate = gate, actor Human), advances
    ``current_gate`` to the next gate after Proceed* (unchanged after Hold), writes audit events (Human)
    and returns the review, ``new_current_gate`` and created condition ids."""
    transition = _transition(db, transition_id)
    _valid_gate(gate)
    review, created, new_gate = gate_actions.record_stage_review(
        db,
        transition=transition,
        gate=gate,
        outcome=body.outcome,
        note=body.note,
        conditions=body.conditions,
        user=user,
    )
    db.commit()
    db.refresh(review)
    return GateReviewOut(
        review=_record(db, review), new_current_gate=new_gate, conditions_created=created
    )


@router.post(
    "/transitions/{transition_id}/gates/{gate}/request-approval",
    response_model=GateApprovalRequestOut,
    responses=_ERR,
)
def request_approval(
    transition_id: str,
    gate: str,
    body: GateApprovalRequestIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.SEND_DRAFTS)),
) -> GateApprovalRequestOut:
    """Request the AtD (OLM -> IRM) or AtO (IRM -> OLM) approval chain (BR-040 point 2, BR-041).

    403 unless the transition's OR focal (Perm.SEND_DRAFTS). 404 unknown transition or ``draft_id``.
    409 (reasons[]) when the gate is not a decision gate, is not the current gate, a Pending/Approved
    chain already exists, the readiness verdict is "Not ready" (reasons = the blockers), the
    transition is Closed, or ``draft_id`` is not an open request-approval draft of this transition and
    gate. 422 for ``approvers`` that do not match a step role. Delegates to
    ``domain.gate_actions.request_gate_approval``; the draft (if any) is marked Sent (audited)."""
    transition = _transition(db, transition_id)
    _valid_gate(gate)
    if body.draft_id is not None and db.get(OrionDraft, body.draft_id) is None:
        raise NotFound(f"Draft {body.draft_id} not found")
    approvers = body.approvers  # validated against the step roles when the chain is created
    request = gate_actions.request_gate_approval(
        db,
        transition=transition,
        gate=gate,
        user=user,
        note=body.note or "",
        via_draft_id=body.draft_id,
        approvers=approvers,
    )
    db.commit()
    db.refresh(request)
    out = approval_out(request, {u.id: u for u in db.query(User).all()})
    return GateApprovalRequestOut(
        request_id=request.id, status=request.status, steps=out.steps if out else []
    )


@router.post(
    "/transitions/{transition_id}/gates/{gate}/decision",
    response_model=GateReviewOut,
    responses=_ERR,
)
def record_decision(
    transition_id: str,
    gate: str,
    body: GateDecisionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.RECORD_GATE_DECISION)),
) -> GateReviewOut:
    """Record a decision-gate / closure outcome (BR-040 decision gates, points 3-8).

    403 unless the transition's OR focal (Perm.RECORD_GATE_DECISION); an Admin has no override. 404 unknown transition. 409 (reasons[]) when the gate
    is not SG4_ATD / SG6_ATO / CLOSURE, is not the current gate, or ``rules.gates.validate_decision``
    disallows the outcome (chain not Approved, open uncovered items, Critical gaps, Compliance rule,
    failed evals at SG4_ATD, AtO extras, closure rules). Decisions per gate: Approve / Approve with
    conditions / Return (AtD, AtO) and Close / Return (CLOSURE; conditions not allowed). 422 for an
    unknown decision, Return without a note, or invalid conditions (due gate must be later than the gate).
    Return cancels the open approval chain (steps Cancelled) and keeps the gate. Approve* creates the
    conditions (Human) and advances the gate (AtD -> Hypercare, AtO -> Closure); Close sets the
    transition status to Closed. Audit events (Human). Returns the GateReview record."""
    transition = _transition(db, transition_id)
    _valid_gate(gate)
    review, created, new_gate, closed = gate_actions.record_decision(
        db,
        transition=transition,
        gate=gate,
        decision=body.decision,
        note=body.note,
        conditions=body.conditions,
        user=user,
    )
    db.commit()
    db.refresh(review)
    return GateReviewOut(
        review=_record(db, review),
        new_current_gate=new_gate,
        conditions_created=created,
        transition_closed=closed,
    )
