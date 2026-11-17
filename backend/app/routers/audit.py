"""Audit trail: GET /audit (FR-110). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["audit"], dependencies=[Depends(get_current_user)])
