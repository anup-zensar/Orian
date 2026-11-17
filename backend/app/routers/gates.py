"""Gates: readiness check, stage reviews, request approval, decisions (FR-034, FR-050, BR-040). M5."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["gates"], dependencies=[Depends(get_current_user)])
