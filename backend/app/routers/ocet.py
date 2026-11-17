"""OCET module (FR-060, BR-070). M6."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["ocet"], dependencies=[Depends(get_current_user)])
