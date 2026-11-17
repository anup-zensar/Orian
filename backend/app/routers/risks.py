"""Risks: /transitions/{id}/risks (FR-035). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.records import RiskCreateIn, RiskOut

router = APIRouter(tags=["risks"], dependencies=[Depends(get_current_user)])


@router.get("/transitions/{transition_id}/risks", response_model=list[RiskOut])
def list_risks(
    transition_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RiskOut]:
    """Risk register of a transition (spec 8.7 f), sorted by rating (High, Medium, Low) then id.
    404 unknown transition."""
    from app.domain import records

    return records.list_risks(db, transition_id)


@router.post("/transitions/{transition_id}/risks", response_model=RiskOut, status_code=201)
def create_risk(
    transition_id: str,
    body: RiskCreateIn,
    user: User = Depends(require(Perm.MANAGE_RISKS)),
    db: Session = Depends(get_db),
) -> RiskOut:
    """Add a risk ``CR-nn`` (``next_id``).

    * 403 without ``Perm.MANAGE_RISKS`` (OR focal, IRM); 404 unknown transition.
    * 422: blank title; ``item_ids`` entries that are not items of this transition.
    * One AuditEvent (entity "Risk", action "created", Human). 201 with ``RiskOut``.
    """
    from app.domain import records

    result = records.create_risk(db, transition_id, body, user)
    db.commit()
    return result
