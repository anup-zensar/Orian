"""Audit trail rows (NFR-03; dashboard recent activity §8.1, workspace Activity tab §8.7 k, FR-110)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AuditEventOut(BaseModel):
    id: int
    at: datetime
    actor_user_id: str | None
    actor_name: str | None  # resolved user name; None for Workflow rule / System without a user
    actor_type: str  # Human | Workflow rule | Orion agent | System
    transition_id: str | None
    transition_name: str | None
    entity: str
    entity_id: str
    action: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    note: str
    summary: str = ""  # human-readable one-liner, e.g. "Drafted Orion draft 1"


class AuditFilters(BaseModel):
    """Query filters for ``GET /audit`` (spec §8.17). All optional, AND-combined; newest first."""

    model_config = ConfigDict(populate_by_name=True)

    transition_id: str | None = None
    actor: str | None = Field(default=None, description="Actor user id")
    actor_type: Literal["Human", "Workflow rule", "Orion agent", "System"] | None = None
    entity: str | None = Field(
        default=None, description="Entity name, e.g. TransitionItem, Condition"
    )
    from_date: date | None = Field(
        default=None, alias="from", description="Inclusive, by event date"
    )
    to_date: date | None = Field(default=None, alias="to", description="Inclusive, by event date")
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class AuditPageOut(BaseModel):
    items: list[AuditEventOut]
    total: int  # matching rows before limit/offset
    # Every entity name in the trail (of the transition when ``transition_id`` is set), sorted, for the
    # Entity filter; the other filters and the paging do not narrow it.
    entities: list[str] = []
