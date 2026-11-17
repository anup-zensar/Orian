"""Conditions: /transitions/{id}/conditions, PATCH /conditions/{cid} (FR-035). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.records import ConditionCreateIn, ConditionOut, ConditionPatchIn

router = APIRouter(tags=["conditions"], dependencies=[Depends(get_current_user)])


@router.get("/transitions/{transition_id}/conditions", response_model=list[ConditionOut])
def list_conditions(
    transition_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConditionOut]:
    """Conditions of a transition (spec 8.7 f): Open first (by due gate order), then Closed (newest
    closed first). 404 unknown transition. ``covers_now`` = status Open and ``due_gate`` strictly after
    the transition's ``current_gate`` (GATE_ORDER). Gate shorts from ``GATE_SHORT``."""
    from app.domain import records

    return records.list_conditions(db, transition_id)


@router.post(
    "/transitions/{transition_id}/conditions", response_model=ConditionOut, status_code=201
)
def create_condition_endpoint(
    transition_id: str,
    body: ConditionCreateIn,
    user: User = Depends(require(Perm.MANAGE_CONDITIONS)),
    db: Session = Depends(get_db),
) -> ConditionOut:
    """Add a condition by hand (the ... menu "add condition", spec 8.7 b/f). Delegates to
    ``app.domain.conditions.create_condition`` with set_at_gate = transition.current_gate, actor Human.

    * 403 without ``Perm.MANAGE_CONDITIONS`` (OR focal, IRM); 404 unknown transition or ``item_id`` not an
      item of this transition.
    * 422: unknown owner, unknown ``due_gate``, due gate before the current gate, blank text.
    * 409 when the transition is Closed.
    """
    from app.domain import records

    result = records.create_manual_condition(db, transition_id, body, user)
    db.commit()
    return result


@router.patch("/conditions/{condition_id}", response_model=ConditionOut)
def patch_condition(
    condition_id: str,
    body: ConditionPatchIn,
    user: User = Depends(require(Perm.MANAGE_CONDITIONS)),
    db: Session = Depends(get_db),
) -> ConditionOut:
    """Close a condition (``status`` "Closed" + ``close_note``) or edit owner / due_gate / text.

    * 403 without ``Perm.MANAGE_CONDITIONS``; 404 unknown condition.
    * 422: closing without ``close_note``; unknown owner / gate; due gate before ``set_at_gate``.
    * 409: any edit of an already Closed condition ("Condition is already closed").
    * Closing sets ``closed_by`` = user, ``closed_at`` = clock.now(); AuditEvent (entity "Condition",
      action "closed" or "updated", before/after, Human). Closing does NOT change the item's status; the
      item is no longer covered and counts as open again (BR-020).
    """
    from app.domain import records

    result = records.patch_condition(db, condition_id, body, user)
    db.commit()
    return result
