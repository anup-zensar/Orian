"""Admin configuration + demo controls (FR-100). M9."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["admin"], dependencies=[Depends(get_current_user)])
