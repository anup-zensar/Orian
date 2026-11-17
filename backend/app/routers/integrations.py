"""Mock integrations: ServiceNow project lookup, Confluence fetch (spec §9, §10.5). M3/M7."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.schemas.intake import ServiceNowProjectOut

router = APIRouter(tags=["integrations"], dependencies=[Depends(get_current_user)])


@router.get("/integrations/servicenow/projects/{project_id}", response_model=ServiceNowProjectOut)
def get_servicenow_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ServiceNowProjectOut:
    """Mock ServiceNow lookup for the intake "Fetch" button (spec §8.4).

    Uses ``ServiceNowService.get_project`` (services factory). The id is trimmed and upper-cased.
    Returns name, project_type, investment_type, delivery_method, portfolio, region, market,
    description and pm_name; ``pm_user_id`` is the id of the user with role PM whose name matches
    ``pm_name`` case-insensitively (None when no match). 404 detail exactly
    "Not found in ServiceNow (mock) – enter manually" when unknown. Any signed-in role.
    """
    from app.domain.intake import lookup_servicenow

    return lookup_servicenow(db, project_id)
