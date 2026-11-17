"""GET /control-tower (spec §8.2, FR-011)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain.control_tower import build_control_tower
from app.models import User
from app.schemas.control_tower import ControlTowerOut
from app.schemas.transitions import TransitionFilters

router = APIRouter(tags=["control-tower"], dependencies=[Depends(get_current_user)])


@router.get("/control-tower", response_model=ControlTowerOut)
def get_control_tower(
    filters: Annotated[TransitionFilters, Query()],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ControlTowerOut:
    """Portfolio-wide view over the filtered transitions: KPI tiles (active, red, decisions <= 14 days,
    with critical gaps, compliance readiness < 70 %), heatmap portfolio x gate (count + worst RAG),
    readiness by region, the register (``transitions``), escalation queue, decision calendar (45 days), operating rhythm.
    """
    return build_control_tower(db, user, filters)
