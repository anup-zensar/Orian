"""GET /control-tower (spec §8.2, FR-011). M2."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["control-tower"], dependencies=[Depends(get_current_user)])
