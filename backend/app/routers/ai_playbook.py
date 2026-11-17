"""AI playbook tab: eval targets/results, import eval results (mock) (FR-037). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["ai-playbook"], dependencies=[Depends(get_current_user)])
