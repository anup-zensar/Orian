"""Transitions: list/create/get/patch, autonomous mode (spec §9; FR-012, FR-020, FR-030). M2/M3/M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["transitions"], dependencies=[Depends(get_current_user)])
