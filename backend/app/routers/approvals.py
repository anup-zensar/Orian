"""Approvals: GET /approvals, approve/reject steps (FR-070, BR-041). M5."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.deps import IdPath, get_current_user, get_db
from app.domain import approvals as domain
from app.errors import Forbidden, NotFound
from app.models import ApprovalRequest, ApprovalStep, Transition, User
from app.permissions import DENIAL_REASONS, Perm, has_perm
from app.rules.constants import GATE_SHORT
from app.schemas.approvals import (
    ApprovalDecisionIn,
    ApprovalRejectIn,
    ApprovalRequestOut,
    ApprovalStepOut,
)
from app.schemas.common import PersonRef

router = APIRouter(tags=["approvals"], dependencies=[Depends(get_current_user)])


def _person(users: dict[str, User], user_id: str | None) -> PersonRef | None:
    if not user_id:
        return None
    user = users.get(user_id)
    return PersonRef(id=user_id, name=user.name if user else user_id)


def approval_out(db: Session, request: ApprovalRequest, viewer: User) -> ApprovalRequestOut:
    """DTO for one request with ``can_act`` etc. computed for ``viewer`` (also used by other areas)."""
    ids = {request.created_by} if request.created_by else set()
    for s in request.steps:
        ids.update(i for i in (s.approver_user_id, s.decided_by) if i)
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).all()} if ids else {}
    transition = db.get(Transition, request.transition_id)
    today = clock.today()

    steps = [
        ApprovalStepOut(
            step=s.step,
            role=s.role,
            label=s.label,
            approver=_person(users, s.approver_user_id),
            status=s.status,  # type: ignore[arg-type]
            activated_at=s.activated_at,
            decided_at=s.decided_at,
            decided_by=_person(users, s.decided_by),
            comment=s.comment,
            waiting_days=(
                max((today - s.activated_at.date()).days, 0)
                if s.status == "Pending" and s.activated_at
                else 0
            ),
        )
        for s in request.steps
    ]
    current = domain.current_step(request) if request.status == "Pending" else None
    can_act = False
    denied: str | None = None
    if request.status == "Pending" and current is not None:
        denied = domain.act_denied_reason(db, current, viewer)
        can_act = denied is None
    return ApprovalRequestOut(
        id=request.id,
        type=request.type,  # type: ignore[arg-type]
        type_label=domain.TYPE_LABELS.get(request.type, request.type),
        transition_id=request.transition_id,
        transition_name=transition.name if transition else request.transition_id,
        gate=request.gate,
        gate_short=GATE_SHORT.get(request.gate, request.gate) if request.gate else None,
        subject_id=request.subject_id,
        subject_label=request.subject_label,
        status=request.status,  # type: ignore[arg-type]
        created_by=_person(users, request.created_by),
        created_source=request.created_source,
        created_at=request.created_at,
        age_days=max((today - request.created_at.date()).days, 0),
        steps=steps,
        current_step=current.step if current else None,
        can_act=can_act,
        act_denied_reason=denied if request.status == "Pending" and not can_act else None,
        is_mock_step=bool(current and domain.is_mock_step(db, current)),
        link=domain.subject_link(request),
    )


def _involves(db: Session, step: ApprovalStep, user: User) -> bool:
    """The step is the user's: named approver, decider, same role, or the mock step for a role that
    may see mock approvals (IRM)."""
    return (
        step.approver_user_id == user.id
        or step.decided_by == user.id
        or step.role == user.role
        or (domain.is_mock_step(db, step) and has_perm(user.role, Perm.SEE_MOCK_APPROVALS))
    )


def _load(db: Session, request_id: str) -> ApprovalRequest:
    request = db.get(ApprovalRequest, request_id)
    if request is None:
        raise NotFound(f"Approval request {request_id} not found")
    return request


@router.get("/approvals", response_model=list[ApprovalRequestOut])
def list_approvals(
    scope: Literal["mine", "requested", "all"] = Query(default="mine"),
    status: str | None = Query(default=None, description="Pending|Approved|Rejected|Cancelled"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApprovalRequestOut]:
    """Approval requests, newest first (FR-070).

    * mine: requests with a Pending step the user can act on (step approver == user, or step role
      == user role; IRM also sees the CISO_BISO mock step), plus the user's finished ones when
      ``status`` is given.
    * requested: requests created_by the user.
    * all: every request; only roles with "view all approvals" (OR_FOCAL, ADMIN), else 403 "Only the OR focal or Admin can see
      all approvals".
    ``can_act``, ``act_denied_reason``, ``is_mock_step`` are computed for the calling user.
    """
    if scope == "all" and not has_perm(user.role, Perm.VIEW_ALL_APPROVALS):
        raise Forbidden(DENIAL_REASONS[Perm.VIEW_ALL_APPROVALS])
    query = select(ApprovalRequest).order_by(
        ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc()
    )
    if status:
        query = query.where(ApprovalRequest.status == status)
    rows = list(db.scalars(query).all())
    if scope == "requested":
        rows = [r for r in rows if r.created_by == user.id]
    elif scope == "mine":
        if status:
            rows = [r for r in rows if any(_involves(db, s, user) for s in r.steps)]
        else:
            rows = [
                r
                for r in rows
                if r.status == "Pending"
                and (cur := domain.current_step(r)) is not None
                and _involves(db, cur, user)
            ]
    return [approval_out(db, r, user) for r in rows]


@router.get("/approvals/{request_id}", response_model=ApprovalRequestOut)
def get_approval(
    request_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApprovalRequestOut:
    """One approval request with its steps. 404 if unknown."""
    return approval_out(db, _load(db, request_id), user)


@router.post("/approvals/{request_id}/steps/{step}/approve", response_model=ApprovalRequestOut)
def approve_approval_step(
    request_id: str,
    step: IdPath,
    body: ApprovalDecisionIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApprovalRequestOut:
    """Approve a step via ``domain.approvals.approve_step`` and commit (BR-041).

    404 unknown request or step. 403 when the user is not the step's approver/role (reason names
    the required role). 409 when the request is not Pending or the step is not the current one
    (sequential), the subject transition is Closed, or the requester approves their own request while
    DEMO_MODE is off. Notifies the next approver (in-app + mock email + Teams card); the last approval
    completes the request and runs the completion hook for its type.
    """
    request = _load(db, request_id)
    domain.approve_step(
        db, request=request, step=step, user=user, comment=body.comment if body else None
    )
    db.commit()
    return approval_out(db, request, user)


@router.post("/approvals/{request_id}/steps/{step}/reject", response_model=ApprovalRequestOut)
def reject_approval_step(
    request_id: str,
    step: IdPath,
    body: ApprovalRejectIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApprovalRequestOut:
    """Reject a step via ``domain.approvals.reject_step`` and commit. ``comment`` is required
    (422 when blank). Same 403/404/409 rules as approve. The whole request becomes Rejected,
    remaining steps Cancelled, the requester is notified, completion hook runs.
    """
    request = _load(db, request_id)
    domain.reject_step(db, request=request, step=step, user=user, comment=body.comment)
    db.commit()
    return approval_out(db, request, user)
