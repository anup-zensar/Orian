"""Outbox of mock email / Teams messages (FR-072). M5."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["outbox"], dependencies=[Depends(get_current_user)])
