"""Leadership update DTOs (spec §8.14 FR-080, §9)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import PersonRef

LeadershipScope = Literal["transition", "portfolio", "all"]


class LeadershipUpdateOut(BaseModel):
    """A stored leadership update (``LeadershipUpdate`` row). ``content_md`` sections, in order:
    headline, status by portfolio/gate, top risks/blockers, decisions due next 30 days, asks for
    leadership, wins."""

    id: int
    scope: LeadershipScope
    scope_id: str | None = None  # transition id or portfolio name; None for scope=all
    title: str  # e.g. "Leadership update - GCC portfolio"
    content_md: str
    generated_by: PersonRef | None = None
    generated_source: str = "Orion agent"
    created_at: datetime
    sent_at: datetime | None = None
    sent_to: list[str] = []  # recipients of the send (from the audit/outbox record)


class LeadershipUpdateCreateIn(BaseModel):
    """Body of POST /orion/leadership-update."""

    scope: LeadershipScope
    scope_id: str | None = Field(
        default=None,
        description="Transition id (scope=transition) or portfolio name (scope=portfolio); "
        "must be omitted/None for scope=all",
    )


class LeadershipSendIn(BaseModel):
    to: list[str] = Field(min_length=1, description="Recipient email addresses")
