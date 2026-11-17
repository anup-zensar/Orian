"""Conditions: /transitions/{id}/conditions, PATCH /conditions/{cid} (FR-035). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["conditions"], dependencies=[Depends(get_current_user)])
