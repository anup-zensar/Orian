"""Tiering and AI profile: /tiering/propose, /transitions/{id}/tier, /tier/confirm, /ai-profile (FR-021, BR-011). M3."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["tiering"], dependencies=[Depends(get_current_user)])
