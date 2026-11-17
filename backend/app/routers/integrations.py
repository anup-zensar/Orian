"""Mock integrations: ServiceNow project lookup, Confluence fetch (spec §9, §10.5). M3/M7."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["integrations"], dependencies=[Depends(get_current_user)])
