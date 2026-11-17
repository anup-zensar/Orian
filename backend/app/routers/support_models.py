"""Support model generator + PPT export (FR-040). M7."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["support-models"], dependencies=[Depends(get_current_user)])
