"""GET /dashboard – role-aware home (spec §8.1, FR-010)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain.dashboard import build_dashboard
from app.models import User
from app.schemas.dashboard import DashboardOut

router = APIRouter(tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOut:
    """KPI tiles (my open items, my pending approvals, transitions I own (OR focal), decisions due in
    14 days, critical gaps in my transitions), "My work", recent activity; LEADERSHIP gets portfolio
    tiles instead of "My work"."""
    return build_dashboard(db, user)
