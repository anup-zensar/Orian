"""Hypercare defects: /transitions/{id}/defects, PATCH /defects/{did}, confirm-none (FR-036). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.records import (
    ConfirmNoDefectsIn,
    DefectCreateIn,
    DefectOut,
    DefectPatchIn,
    HypercareOut,
)

router = APIRouter(tags=["defects"], dependencies=[Depends(get_current_user)])


@router.get("/transitions/{transition_id}/defects", response_model=HypercareOut)
def get_hypercare(
    transition_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HypercareOut:
    """Hypercare tracker (spec 8.7 g): defects sorted Open first, then priority P1..P4, then id, plus
    ``no_defects_confirmed`` (Transition.hypercare_no_defects_confirmed), ``tracker_in_place`` (at least one
    defect OR no_defects_confirmed) and ``open_p1_p2`` (Open defects of priority P1 or P2). These feed the
    AtO rules and closure items UD-002 / UD-003. 404 unknown transition."""
    from app.domain import records

    return records.get_hypercare(db, transition_id)


@router.post("/transitions/{transition_id}/defects", response_model=DefectOut, status_code=201)
def create_defect(
    transition_id: str,
    body: DefectCreateIn,
    user: User = Depends(require(Perm.MANAGE_DEFECTS)),
    db: Session = Depends(get_db),
) -> DefectOut:
    """Log a defect ``DEF-nnn`` (status Open).

    * 403 without ``Perm.MANAGE_DEFECTS`` (OR focal, PM, Architect, OLM); 404 unknown transition.
    * 422: blank title; unknown owner.
    * 409 when the transition is Closed.
    * Logging a defect resets ``hypercare_no_defects_confirmed`` to false. One AuditEvent (entity
      "HypercareDefect", action "created", Human). 201 with ``DefectOut``.
    """
    from app.domain import records

    result = records.create_defect(db, transition_id, body, user)
    db.commit()
    return result


@router.patch("/defects/{defect_id}", response_model=DefectOut)
def patch_defect(
    defect_id: str,
    body: DefectPatchIn,
    user: User = Depends(require(Perm.MANAGE_DEFECTS)),
    db: Session = Depends(get_db),
) -> DefectOut:
    """Edit a defect (title, priority, status Open/Resolved, owner); only fields in ``model_fields_set``
    are applied. 403 without ``Perm.MANAGE_DEFECTS``; 404 unknown defect; 422 unknown owner / blank title.
    AuditEvent (entity "HypercareDefect", action "updated" or "resolved", before/after, Human)."""
    from app.domain import records

    result = records.patch_defect(db, defect_id, body, user)
    db.commit()
    return result


@router.post("/transitions/{transition_id}/defects/confirm-none", response_model=HypercareOut)
def confirm_no_defects(
    transition_id: str,
    body: ConfirmNoDefectsIn,
    user: User = Depends(require(Perm.MANAGE_DEFECTS)),
    db: Session = Depends(get_db),
) -> HypercareOut:
    """Tick / untick "No defects - tracker in place" (spec 8.7 g).

    * 403 without ``Perm.MANAGE_DEFECTS``; 404 unknown transition.
    * 409 when ``confirmed`` is true while any defect exists ("Resolve or remove defects first": confirming
      "no defects" is only valid for an empty tracker); unticking is always allowed.
    * Sets Transition.hypercare_no_defects_confirmed; AuditEvent (entity "Transition", action
      "hypercare_no_defects_confirmed", before/after, Human). Returns the refreshed ``HypercareOut``.
    """
    from app.domain import records

    result = records.confirm_no_defects(db, transition_id, body, user)
    db.commit()
    return result
