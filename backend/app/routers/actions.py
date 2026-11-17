"""Actions: /transitions/{id}/actions, PATCH /actions/{aid} (FR-032). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.records import ActionCreateIn, ActionOut, ActionPatchIn

router = APIRouter(tags=["actions"], dependencies=[Depends(get_current_user)])


@router.get("/transitions/{transition_id}/actions", response_model=list[ActionOut])
def list_actions(
    transition_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ActionOut]:
    """Actions of a transition (spec 8.7 c). 404 unknown transition. Sorted: Open / In progress first (by
    due date, soonest first, no date last), then Done / Cancelled (newest first).
    ``days_until_due`` = due_date - clock.today(); ``overdue`` = due in the past and status Open /
    In progress."""
    from app.domain import records

    return records.list_actions(db, transition_id)


@router.post("/transitions/{transition_id}/actions", response_model=ActionOut, status_code=201)
def create_action(
    transition_id: str,
    body: ActionCreateIn,
    user: User = Depends(require(Perm.MANAGE_ACTIONS)),
    db: Session = Depends(get_db),
) -> ActionOut:
    """Create an action ``ACT-nnn`` (``next_id``), status "Open", origin "Human", ``created_by`` = user.

    * 403 without ``Perm.MANAGE_ACTIONS``; 404 unknown transition.
    * 422: unknown owner user; any ``item_ids`` entry that is not an item of this transition; blank title.
    * 409 when the transition is Closed.
    * One AuditEvent (entity "Action", action "created", after snapshot, Human). 201 with ``ActionOut``.
    """
    from app.domain import records

    result = records.create_action(db, transition_id, body, user)
    db.commit()
    return result


@router.patch("/actions/{action_id}", response_model=ActionOut)
def patch_action(
    action_id: str,
    body: ActionPatchIn,
    user: User = Depends(require(Perm.MANAGE_ACTIONS)),
    db: Session = Depends(get_db),
) -> ActionOut:
    """Edit or close an action; only fields in ``model_fields_set`` are applied.

    * 403 without ``Perm.MANAGE_ACTIONS``; 404 unknown action; 422 unknown owner / blank title.
    * 409 when a Done or Cancelled action is edited other than reopening it (status Open / In progress).
    * One AuditEvent (entity "Action", action "updated" or "closed" when status becomes Done/Cancelled,
      before/after, Human).
    """
    from app.domain import records

    result = records.patch_action(db, action_id, body, user)
    db.commit()
    return result
