"""Exception (compliance control deviation) DTOs (spec §6 Exception, §8.7 f, FR-035, BR-041)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import PersonRef


class ExceptionOut(BaseModel):
    ref: str  # EX-01
    transition_id: str
    item_id: str | None  # playbook item id (e.g. C-12); None if the linked item was removed
    item_title: str | None
    text: str
    status: str  # Draft | Pending <step role> (derived from the current step) | Approved | Rejected
    approval_request_id: str | None
    requested_by: PersonRef | None
    created_at: datetime


class ExceptionCreateIn(BaseModel):
    item_id: str = Field(
        min_length=1, max_length=40, description="Playbook item id of a Compliance item"
    )
    text: str = Field(min_length=1, max_length=4000)
    # optional approver per chain step {step: user_id}; default from the transition roles (BE#12)
    approvers: dict[int, str] | None = Field(default=None, max_length=10)
