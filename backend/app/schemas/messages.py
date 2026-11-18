"""Orion drafts, outbox and notifications DTOs (spec §6, §8.12 FR-071, §8.13 FR-072, §10)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import PersonRef

DraftStatus = Literal["Draft", "Sent", "Discarded"]


class DraftOut(BaseModel):
    id: int
    transition_id: str | None
    transition_name: str | None
    # Reminder | Chaser | Input request | Approval request | Leadership update
    kind: str
    to: list[str]  # email addresses
    cc: list[str]
    subject: str
    body_html: str
    rule_id: str | None  # R1..R7
    source_label: str  # "Workflow rule R1" (created_source == "Workflow rule") | "Orion agent"
    status: DraftStatus
    created_source: str  # Workflow rule | Orion agent
    created_at: datetime
    sent_by: PersonRef | None
    sent_at: datetime | None
    action: (
        dict[str, Any] | None
    )  # executed on Send, e.g. {"type": "request_approval", "gate": ...}
    related_ids: list[str]
    can_send: bool = True  # the current user may send this draft (per-transition access)
    send_denied_reason: str | None = None
    can_edit: bool = True
    edit_denied_reason: str | None = None


class DraftPatchIn(BaseModel):
    to: list[str] = Field(max_length=100)
    cc: list[str] = Field(default=[], max_length=100)
    subject: str = Field(min_length=1, max_length=300)
    body_html: str = Field(min_length=1, max_length=50000)


class DraftSendResult(BaseModel):
    approval_request_id: str | None = None  # set when the action was request_approval


class DraftSendOut(BaseModel):
    draft: DraftOut  # status Sent, sent_by/sent_at set
    outbox_message_ids: list[int]  # the Email and the Teams outbox rows
    result: DraftSendResult


class ApprovalRequestDraftIn(BaseModel):
    transition_id: str = Field(max_length=40)
    gate: str = Field(
        max_length=40, description="SG4_ATD or the ATO gate code (see rules/constants.py)"
    )


class ChaserDraftIn(BaseModel):
    transition_id: str = Field(max_length=40)
    item_ids: list[str] = Field(
        min_length=1, max_length=200, description="Playbook item ids to chase"
    )


class OutboxMessageOut(BaseModel):
    id: int
    channel: Literal["Email", "Teams"]
    from_address: str
    to: list[str]
    cc: list[str]
    subject: str
    body_html: str
    adaptive_card_json: dict[str, Any] | None
    related_ids: list[str]
    sent_at: datetime
    mode: str  # mock | live
    draft_id: int | None


class NotificationOut(BaseModel):
    id: int
    text: str
    link: str
    read: bool
    created_at: datetime


class NotificationsOut(BaseModel):
    unread: int
    items: list[NotificationOut]  # newest first, current user only, max 50
