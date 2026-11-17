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


class PersonRef(BaseModel):
    """Compact user reference for tables and cards."""

    id: str
    name: str


class LensValues(BaseModel):
    """One integer per lens (readiness %, counts …). Lens colours: Business amber, Technical blue,
    Compliance teal (spec §4, §12)."""

    Business: int
    Technical: int
    Compliance: int


class KpiTileOut(BaseModel):
    """A KPI tile (spec §8.1, §8.2). Control-tower tiles carry ``filter`` (query params that reproduce
    the tile's set – clicking a tile filters the register); dashboard tiles carry ``link`` (a route).
    """

    key: str
    label: str
    value: int
    tone: str = "neutral"  # neutral | danger | warning | info | success
    hint: str = ""  # one-line explanation shown as tooltip
    filter: dict[str, str] = {}
    link: str | None = None
