"""Hypercare defects: /transitions/{id}/defects, PATCH /defects/{did}, confirm-none (FR-036). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["defects"], dependencies=[Depends(get_current_user)])
