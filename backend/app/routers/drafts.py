"""Orion drafts queue: list/edit/send/discard (FR-071). M5/M8."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["drafts"], dependencies=[Depends(get_current_user)])
