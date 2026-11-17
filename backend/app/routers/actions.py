"""Actions: /transitions/{id}/actions, PATCH /actions/{aid} (FR-032). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["actions"], dependencies=[Depends(get_current_user)])
