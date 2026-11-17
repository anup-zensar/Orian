"""Work records on a transition (spec §6 Evidence, Action, Condition, Exception, Risk,
HypercareDefect, EvalResult)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Evidence(TimestampMixin, Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)  # EVD-001
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    transition_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("transition_items.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(
        String(20)
    )  # Document | Link | Email sign-off | Recording | Generated
    url: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)  # relative to STORAGE_DIR
    text: Mapped[str | None] = mapped_column(Text, nullable=True)  # email sign-off text
    submitted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(12), default="Submitted"
    )  # Submitted | Accepted | Rejected
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Action(TimestampMixin, Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)  # ACT-001
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    item_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list
    )  # playbook item ids, e.g. ["S45-014"]
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(12), default="Open"
    )  # Open | In progress | Done | Cancelled
    priority: Mapped[str] = mapped_column(String(8), default="Medium")  # High | Medium | Low
    origin: Mapped[str] = mapped_column(
        String(120), default="Human"
    )  # Human | Orion proposal accepted by <user>
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Condition(TimestampMixin, Base):
    __tablename__ = "conditions"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)  # CON-001
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    transition_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("transition_items.id"), nullable=True, index=True
    )
    set_at_gate: Mapped[str] = mapped_column(String(20))
    due_gate: Mapped[str] = mapped_column(String(20))
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="Open")  # Open | Closed
    closed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    close_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExceptionRecord(TimestampMixin, Base):
    """Compliance control deviation approved by CISO/BISO (mocked). Spec §6 "Exception"."""

    __tablename__ = "exceptions"

    ref: Mapped[str] = mapped_column(String(12), primary_key=True)  # EX-01
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    transition_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("transition_items.id"), nullable=True, index=True
    )
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(24), default="Draft"
    )  # Draft | Pending CISO/BISO | Approved | Rejected
    approval_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("approval_requests.id"), nullable=True
    )
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Risk(TimestampMixin, Base):
    __tablename__ = "risks"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)  # CR-01
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    rating: Mapped[str] = mapped_column(String(8))  # High | Medium | Low
    decision: Mapped[str] = mapped_column(Text, default="")
    item_ids: Mapped[list[str]] = mapped_column(JSON, default=list)  # playbook item ids


class HypercareDefect(TimestampMixin, Base):
    __tablename__ = "hypercare_defects"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)  # DEF-001
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    priority: Mapped[str] = mapped_column(String(4))  # P1 | P2 | P3 | P4
    status: Mapped[str] = mapped_column(String(10), default="Open")  # Open | Resolved
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class EvalResult(TimestampMixin, Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    metric_id: Mapped[str] = mapped_column(String(10))  # EV-03
    value_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    passed: Mapped[bool | None] = mapped_column("pass", Boolean, nullable=True)  # spec field "pass"
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="Manual")  # Manual | Imported (mock)
