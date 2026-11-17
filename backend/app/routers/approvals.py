"""Approvals: GET /approvals, approve/reject steps (FR-070, BR-041). M5."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["approvals"], dependencies=[Depends(get_current_user)])
