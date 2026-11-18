"""Orion drafts queue: list/edit/send/discard (FR-071). M5/M8."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import transition_denial
from app.deps import IdPath, get_current_user, get_db, require
from app.domain import drafts as domain
from app.errors import NotFound
from app.models import OrionDraft, Transition, User
from app.permissions import DENIAL_REASONS, Perm, has_perm
from app.schemas.common import PersonRef
from app.schemas.messages import (
    ApprovalRequestDraftIn,
    ChaserDraftIn,
    DraftOut,
    DraftPatchIn,
    DraftSendOut,
    DraftSendResult,
)

router = APIRouter(tags=["drafts"], dependencies=[Depends(get_current_user)])


def _use_denial(db: Session, user: User, transition: Transition | None) -> str | None:
    """Reason the user may not send or edit drafts (None = allowed); role-level without a transition."""
    if transition is None:
        return None if has_perm(user.role, Perm.SEND_DRAFTS) else DENIAL_REASONS[Perm.SEND_DRAFTS]
    reason = transition_denial(db, user, transition, Perm.SEND_DRAFTS)
    if reason is None and transition.status == "Closed":
        reason = f"{transition.id} is closed - records can no longer be added or changed"
    return reason


def draft_out(db: Session, draft: OrionDraft, user: User) -> DraftOut:
    transition = db.get(Transition, draft.transition_id) if draft.transition_id else None
    denial = None if draft.status != "Draft" else _use_denial(db, user, transition)
    sender = db.get(User, draft.sent_by) if draft.sent_by else None
    if draft.created_source == "Workflow rule":
        label = f"Workflow rule {draft.rule_id}" if draft.rule_id else "Workflow rule"
    else:
        label = "Orion agent"
    return DraftOut(
        id=draft.id,
        transition_id=draft.transition_id,
        transition_name=transition.name if transition else None,
        kind=draft.kind,
        to=list(draft.to or []),
        cc=list(draft.cc or []),
        subject=draft.subject,
        body_html=draft.body_html,
        rule_id=draft.rule_id,
        source_label=label,
        status=draft.status,  # type: ignore[arg-type]
        created_source=draft.created_source,
        created_at=draft.created_at,
        sent_by=PersonRef(id=sender.id, name=sender.name) if sender else None,
        sent_at=draft.sent_at,
        action=draft.action,
        related_ids=list(draft.related_ids or []),
        can_send=denial is None and draft.status == "Draft",
        send_denied_reason=denial,
        can_edit=denial is None and draft.status == "Draft",
        edit_denied_reason=denial,
    )


def _load(db: Session, draft_id: int) -> OrionDraft:
    draft = db.get(OrionDraft, draft_id)
    if draft is None:
        raise NotFound(f"Draft {draft_id} not found")
    return draft


def _transition(db: Session, transition_id: str) -> Transition:
    transition = db.get(Transition, transition_id)
    if transition is None:
        raise NotFound(f"Transition {transition_id} not found")
    return transition


@router.get("/orion/drafts", response_model=list[DraftOut])
def list_drafts(
    status: Literal["Draft", "Sent", "Discarded"] | None = Query(default=None),
    kind: str | None = Query(default=None, description="Reminder|Chaser|Input request|..."),
    transition_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DraftOut]:
    """Drafts, newest first, filtered by the optional params (FR-071). Readable by every role."""
    query = select(OrionDraft).order_by(OrionDraft.created_at.desc(), OrionDraft.id.desc())
    if status:
        query = query.where(OrionDraft.status == status)
    if kind:
        query = query.where(OrionDraft.kind == kind)
    if transition_id:
        query = query.where(OrionDraft.transition_id == transition_id)
    return [draft_out(db, d, user) for d in db.scalars(query).all()]


# Static POST paths are declared before /orion/drafts/{draft_id}/... routes for clarity.
@router.post("/orion/drafts/approval-request", response_model=DraftOut, status_code=201)
def draft_approval_request(
    body: ApprovalRequestDraftIn,
    user: User = Depends(require(Perm.SEND_DRAFTS)),
    db: Session = Depends(get_db),
) -> DraftOut:
    """Orion drafts the AtD/AtO approval request email (BR-050: nothing is sent).

    404 unknown transition. 422 when ``gate`` is not an approval gate (SG4_ATD / the ATO gate).
    409 when the gate is not ready to request approval or a Pending request exists (reasons from
    the gate-actions domain). Creates a draft: kind "Approval request", created_source "Orion
    agent", to = approvers of the chain's first step, cc = OR focal, text via
    ``AIService.draft_message``, action {"type": "request_approval", "gate": gate}. Returns 201.
    """
    transition = _transition(db, body.transition_id)
    draft = domain.draft_approval_request(db, transition=transition, gate=body.gate, user=user)
    db.commit()
    return draft_out(db, draft, user)


@router.post("/orion/drafts/chaser", response_model=DraftOut, status_code=201)
def draft_chaser(
    body: ChaserDraftIn,
    user: User = Depends(require(Perm.SEND_DRAFTS)),
    db: Session = Depends(get_db),
) -> DraftOut:
    """Orion drafts a chaser for open items (spec 10.1 template, BR-050: nothing is sent).

    404 unknown transition. 422 when ``item_ids`` are not items of the transition or are Done.
    Creates a draft: kind "Chaser", created_source "Orion agent", to = the items' owners (unique
    emails), cc = OR focal, subject/body from ``AIService.draft_message("chaser", ctx)``,
    related_ids = [transition_id, *item_ids]. Returns 201.
    """
    transition = _transition(db, body.transition_id)
    draft = domain.draft_chaser(db, transition=transition, item_ids=body.item_ids, user=user)
    db.commit()
    return draft_out(db, draft, user)


@router.get("/orion/drafts/{draft_id}", response_model=DraftOut)
def get_draft(
    draft_id: IdPath,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DraftOut:
    """One draft. 404 if unknown."""
    return draft_out(db, _load(db, draft_id), user)


@router.patch("/orion/drafts/{draft_id}", response_model=DraftOut)
def edit_draft(
    draft_id: IdPath,
    body: DraftPatchIn,
    user: User = Depends(require(Perm.SEND_DRAFTS)),
    db: Session = Depends(get_db),
) -> DraftOut:
    """Edit to/cc/subject/body of a draft before sending. 404 unknown; 409 unless status is Draft;
    422 when ``to`` is empty or an address is malformed. Audited (Human). Commits.
    """
    draft = domain.edit_draft(
        db,
        draft=_load(db, draft_id),
        user=user,
        to=body.to,
        cc=body.cc,
        subject=body.subject,
        body_html=body.body_html,
    )
    db.commit()
    return draft_out(db, draft, user)


@router.post("/orion/drafts/{draft_id}/send", response_model=DraftSendOut)
def send_draft_endpoint(
    draft_id: IdPath,
    user: User = Depends(require(Perm.SEND_DRAFTS)),
    db: Session = Depends(get_db),
) -> DraftSendOut:
    """Human send via ``domain.drafts.send_draft`` (BR-050): executes the draft action (e.g.
    request_approval -> ``domain.gate_actions.request_gate_approval``) then sends mock email +
    Teams card; draft becomes Sent. 403 unless the OR focal of the draft's transition. 404 unknown; 409 when not Draft or the action is blocked
    (reasons returned). Commits. ``result.approval_request_id`` set for approval-request drafts.
    """
    draft, message_ids, result = domain.send_draft(db, draft=_load(db, draft_id), user=user)
    db.commit()
    return DraftSendOut(
        draft=draft_out(db, draft, user),
        outbox_message_ids=message_ids,
        result=DraftSendResult(approval_request_id=result.get("approval_request_id")),
    )


@router.post("/orion/drafts/{draft_id}/discard", response_model=DraftOut)
def discard_draft(
    draft_id: IdPath,
    user: User = Depends(require(Perm.SEND_DRAFTS)),
    db: Session = Depends(get_db),
) -> DraftOut:
    """Discard a draft (status Discarded, audited, never sent). 404 unknown; 409 unless Draft."""
    draft = domain.discard_draft(db, draft=_load(db, draft_id), user=user)
    db.commit()
    return draft_out(db, draft, user)
