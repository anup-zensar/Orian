"""Orion agent artefacts, messaging and audit (spec §6 OrionDraft, OutboxMessage, Notification,
AuditEvent, LeadershipUpdate) + stored proposals (BR-050) and reminder runs (BR-060)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app import clock
from app.db import Base, TimestampMixin


class OrionDraft(TimestampMixin, Base):
    """Assistive-mode queue: nothing is sent until a human clicks Send (BR-050)."""

    __tablename__ = "orion_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str | None] = mapped_column(
        ForeignKey("transitions.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(30)
    )  # Reminder | Chaser | Input request | Approval request | Leadership update
    to: Mapped[list[str]] = mapped_column(JSON, default=list)  # email addresses
    cc: Mapped[list[str]] = mapped_column(JSON, default=list)
    subject: Mapped[str] = mapped_column(String(300))
    body_html: Mapped[str] = mapped_column(Text)
    rule_id: Mapped[str | None] = mapped_column(String(4), nullable=True)  # R1..R7
    status: Mapped[str] = mapped_column(String(12), default="Draft")  # Draft | Sent | Discarded
    created_source: Mapped[str] = mapped_column(String(20))  # Workflow rule | Orion agent
    recipient_key: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )  # de-dup key (BR-060)
    # Optional follow-up executed on Send by the human sender, e.g.
    # {"type": "request_approval", "gate": "SG4_ATD"} or {"type": "mark_inputs_requested", "line_ids": [..]}
    action: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    related_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    sent_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_autonomously: Mapped[bool] = mapped_column(Boolean, default=False)


class OrionProposal(TimestampMixin, Base):
    """A recommendation card with a button. Executed only by a permitted human (BR-050)."""

    __tablename__ = "orion_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str | None] = mapped_column(
        ForeignKey("transitions.id"), nullable=True, index=True
    )
    # create_action | draft_chaser | request_inputs | open_ocet | create_support_model |
    # request_exception | request_approval | accept_applicability
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(12), default="Open")  # Open | Accepted | Dismissed
    accepted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class OutboxMessage(TimestampMixin, Base):
    """Every message "sent" through the mock MailService / NotificationService (FR-072)."""

    __tablename__ = "outbox_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(10))  # Email | Teams
    from_address: Mapped[str] = mapped_column(String(200))
    to: Mapped[list[str]] = mapped_column(JSON, default=list)
    cc: Mapped[list[str]] = mapped_column(JSON, default=list)
    subject: Mapped[str] = mapped_column(String(300))
    body_html: Mapped[str] = mapped_column(Text, default="")
    adaptive_card_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    related_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
    mode: Mapped[str] = mapped_column(String(10), default="mock")
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("orion_drafts.id"), nullable=True)


class Notification(TimestampMixin, Base):
    """In-app bell notification."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(300), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditEvent(Base):
    """Append-only audit trail (NFR-03). ``actor_type``: Human | Workflow rule | Orion agent | System."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=clock.now, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), index=True)
    transition_id: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    entity: Mapped[str] = mapped_column(String(40), index=True)  # e.g. TransitionItem
    entity_id: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(60))  # e.g. status_changed
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


class LeadershipUpdate(TimestampMixin, Base):
    __tablename__ = "leadership_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(12))  # transition | portfolio | all
    scope_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    content_md: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReminderRun(TimestampMixin, Base):
    """One execution of the reminder engine (manual button, demo control or scheduler)."""

    __tablename__ = "reminder_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=clock.now)
    triggered_by: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # user id or "scheduler"
    created_counts: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)  # {"R1": 3, ...}
    sent_autonomously: Mapped[int] = mapped_column(Integer, default=0)
