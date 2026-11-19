"""Exceptions: /transitions/{id}/exceptions (POST creates approval chain) (FR-035, BR-041). M4/M5."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import ensure_transition_role
from app.deps import get_current_user, get_db, require
from app.domain import audit
from app.domain.approvals import (
    create_approval_request,
    exception_status,
    pending_status_label,
    validate_approvers,
)
from app.domain.ids import next_id
from app.errors import BadRequest, Conflict, NotFound
from app.models import ExceptionRecord, Transition, TransitionItem, User
from app.permissions import Perm
from app.schemas.common import PersonRef
from app.schemas.exceptions import ExceptionCreateIn, ExceptionOut

router = APIRouter(tags=["exceptions"], dependencies=[Depends(get_current_user)])


def _transition(db: Session, transition_id: str) -> Transition:
    transition = db.get(Transition, transition_id)
    if transition is None:
        raise NotFound(f"Transition {transition_id} not found")
    return transition


def exception_out(db: Session, record: ExceptionRecord) -> ExceptionOut:
    item = db.get(TransitionItem, record.transition_item_id) if record.transition_item_id else None
    requester = db.get(User, record.requested_by) if record.requested_by else None
    return ExceptionOut(
        ref=record.ref,
        transition_id=record.transition_id,
        item_id=item.playbook_item_id if item else None,
        item_title=item.playbook_item.title if item else None,
        text=record.text,
        status=exception_status(db, record),  # derived from the current approval step
        approval_request_id=record.approval_request_id,
        requested_by=PersonRef(id=requester.id, name=requester.name) if requester else None,
        created_at=record.created_at,
    )


@router.get("/transitions/{transition_id}/exceptions", response_model=list[ExceptionOut])
def list_exceptions(
    transition_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ExceptionOut]:
    """Exceptions of a transition ordered by ref (spec 8.7 f). 404 if the transition is unknown."""
    _transition(db, transition_id)
    rows = db.scalars(
        select(ExceptionRecord)
        .where(ExceptionRecord.transition_id == transition_id)
        .order_by(ExceptionRecord.ref)
    ).all()
    return [exception_out(db, r) for r in rows]


@router.post(
    "/transitions/{transition_id}/exceptions", response_model=ExceptionOut, status_code=201
)
def create_exception(
    transition_id: str,
    body: ExceptionCreateIn,
    user: User = Depends(require(Perm.REQUEST_EXCEPTION)),
    db: Session = Depends(get_db),
) -> ExceptionOut:
    """Request an exception for a Compliance item (BR-041, FR-035).

    404 unknown transition. 422 when ``item_id`` is not a playbook item of this transition's
    scope. 409 when the item's lens is not Compliance (reason "Exceptions apply to Compliance
    items only") or a Pending exception already exists for the item. Creates ExceptionRecord
    (ref via next_id "EX-", status "Pending <step role>", requested_by user) and the EXCEPTION
    approval chain (IRM -> CISO_BISO) through ``domain.approvals.create_approval_request`` with
    subject_id=ref; stores approval_request_id; audits; commits. Returns 201.
    """
    transition = _transition(db, transition_id)
    ensure_transition_role(db, user, transition, Perm.REQUEST_EXCEPTION)
    validate_approvers(db, "EXCEPTION", body.approvers)
    item = db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == transition_id,
            TransitionItem.playbook_item_id == body.item_id,
        )
    ).first()
    if item is None:
        raise BadRequest(
            "Unknown item", [f"{body.item_id} is not an item in the scope of {transition_id}"]
        )
    if item.playbook_item.lens != "Compliance":
        raise Conflict("Exceptions apply to Compliance items only")
    existing = db.scalars(
        select(ExceptionRecord).where(
            ExceptionRecord.transition_item_id == item.id,
            ExceptionRecord.status.like("Pending%"),
        )
    ).first()
    if existing is not None:
        raise Conflict(
            "An exception is already pending",
            [f"{existing.ref} is already pending for {body.item_id}"],
        )

    record = ExceptionRecord(
        ref=next_id(db, ExceptionRecord.ref, "EX-"),
        transition_id=transition_id,
        transition_item_id=item.id,
        text=body.text.strip(),
        status="Pending",  # replaced by the label of the first step once the chain exists
        requested_by=user.id,
    )
    db.add(record)
    db.flush()
    request = create_approval_request(
        db,
        type="EXCEPTION",
        transition=transition,
        created_by=user,
        created_source="Human",
        subject_id=record.ref,
        subject_label=f"{record.ref}: {record.text}",
        approvers=body.approvers,
    )
    record.approval_request_id = request.id
    first = next((s for s in request.steps if s.status == "Pending"), None)
    if first is not None:
        record.status = pending_status_label(db, first)[:24]
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="ExceptionRecord",
        entity_id=record.ref,
        action="created",
        transition_id=transition_id,
        after={
            "item_id": body.item_id,
            "status": record.status,
            "approval_request_id": request.id,
        },
        note=f"Exception requested for {body.item_id}",
    )
    db.commit()
    return exception_out(db, record)
