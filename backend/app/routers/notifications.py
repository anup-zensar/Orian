"""In-app notifications (bell). M5."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["notifications"], dependencies=[Depends(get_current_user)])
