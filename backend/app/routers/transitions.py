"""Transitions: list/create/get/patch, autonomous mode (spec §9; FR-012, FR-020, FR-030).

M2 implements ``GET /transitions``; create/get/patch arrive in M3/M4.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain.metrics import to_summary
from app.domain.transitions import filter_transitions
from app.models import User
from app.schemas.transitions import TransitionFilters, TransitionSummaryOut

router = APIRouter(tags=["transitions"], dependencies=[Depends(get_current_user)])


@router.get("/transitions", response_model=list[TransitionSummaryOut])
def list_transitions(
    request: Request,
    filters: Annotated[TransitionFilters, Query()],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransitionSummaryOut]:
    """All transitions matching ``filters`` with live readiness per lens, gaps, RAG and next decision
    (FR-012, BR-020, BR-021). Sorted by days to next decision (soonest first, no date last), then name.

    Besides the named filters, ``?cf_<key>=value`` keeps transitions whose custom field ``cf_<key>``
    (an "Additional details" field added by the Admin) equals ``value`` (for a multiselect field: contains it).
    """
    custom = {k: v for k, v in request.query_params.items() if k.startswith("cf_")}
    rows = filter_transitions(db, user, filters, custom)
    return [to_summary(m) for m in rows]
