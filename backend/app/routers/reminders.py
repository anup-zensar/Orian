"""Reminder engine: POST /reminders/run (BR-060). M8."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["reminders"], dependencies=[Depends(get_current_user)])
