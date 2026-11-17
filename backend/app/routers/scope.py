"""Scope and launch: /transitions/{id}/scope, /launch-assessment (FR-022, BR-010). M3."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["scope"], dependencies=[Depends(get_current_user)])
