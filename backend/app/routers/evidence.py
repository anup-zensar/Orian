"""Evidence: /transitions/{id}/evidence, /evidence/{eid}/review, /evidence/{eid}/download (FR-033). M4."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user

router = APIRouter(tags=["evidence"], dependencies=[Depends(get_current_user)])
