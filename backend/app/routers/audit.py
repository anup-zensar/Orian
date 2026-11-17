"""Audit trail: GET /audit (FR-110). M4."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.schemas.audit import AuditFilters, AuditPageOut

router = APIRouter(tags=["audit"], dependencies=[Depends(get_current_user)])


@router.get("/audit", response_model=AuditPageOut)
def list_audit(
    filters: Annotated[AuditFilters, Query()],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuditPageOut:
    """Global audit trail (spec 8.17, NFR-03; workspace Activity tab uses ``transition_id``). Any signed-in
    user can read it. Newest first (``at`` desc, ``id`` desc).

    * All filters AND-combined. ``from`` / ``to`` are inclusive dates on ``at`` (clock timezone); ``from``
      after ``to`` gives 422. ``entity`` is an exact match; ``actor`` is a user id; ``actor_type`` is
      Human | Workflow rule | Orion agent | System.
    * ``limit`` default 100, max 500; ``offset`` default 0; ``total`` = matching rows before paging.
    * ``actor_name`` and ``transition_name`` are resolved; ``before`` / ``after`` are the stored JSON
      snapshots for the diff view.
    """
    from app.domain.audit_query import query_audit

    return query_audit(db, filters)
