"""Orion agent: chat, insights, proposals, leadership updates (FR-090, FR-080, BR-050). M2/M8."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["orion"], dependencies=[Depends(get_current_user)])
