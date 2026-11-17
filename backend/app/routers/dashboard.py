"""GET /dashboard – role-aware home (spec §8.1, FR-010). M2."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["dashboard"], dependencies=[Depends(get_current_user)])
