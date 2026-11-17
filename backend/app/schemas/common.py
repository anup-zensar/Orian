"""Shared DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for DTOs built from ORM objects (``Model.model_validate(orm_obj)``)."""

    model_config = ConfigDict(from_attributes=True)


class ErrorOut(BaseModel):
    """Error body for 401/403/404/409/422 (see app.errors)."""

    detail: str
    reasons: list[str] = []


class OkOut(BaseModel):
    ok: bool = True
    message: str = ""


class UserOut(ORMModel):
    id: str
    name: str
    email: str
    role: str
    role_label: str = ""
    focal_label: str | None = None


class MeOut(BaseModel):
    user: UserOut
    permissions: list[str]
    # permission code -> human reason (tooltips for disabled controls, spec §12)
    denied_reasons: dict[str, str]
