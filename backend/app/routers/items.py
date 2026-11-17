"""Checklist items: /transitions/{id}/items, PATCH /items/{id}, POST /items/bulk (FR-031, BR-030). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["items"], dependencies=[Depends(get_current_user)])
