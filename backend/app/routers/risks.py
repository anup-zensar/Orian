"""Risks: /transitions/{id}/risks (FR-035). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["risks"], dependencies=[Depends(get_current_user)])
