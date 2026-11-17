"""Exceptions: /transitions/{id}/exceptions (POST creates approval chain) (FR-035, BR-041). M4/M5."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["exceptions"], dependencies=[Depends(get_current_user)])
