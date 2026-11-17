"""Gate reviews and approval chains (spec §6 GateReview, ApprovalRequest; BR-040, BR-041)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin


class GateReview(TimestampMixin, Base):
    __tablename__ = "gate_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    gate: Mapped[str] = mapped_column(String(20))
    gate_type: Mapped[str] = mapped_column(String(20))  # stage_review | decision | closure
    outcome: Mapped[str] = mapped_column(
        String(30)
    )  # Proceed | Proceed with conditions | Hold | Approve | ...
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime)
    note: Mapped[str] = mapped_column(Text, default="")
    conditions_created: Mapped[list[str]] = mapped_column(JSON, default=list)  # condition ids
    approval_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("approval_requests.id"), nullable=True
    )


class ApprovalRequest(TimestampMixin, Base):
    """Sequential approval chain. ``type``: OCET | AtD | AtO | SUPPORT_MODEL | EXCEPTION | RISK_ACCEPTANCE."""

    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)  # APR-0001
    type: Mapped[str] = mapped_column(String(20), index=True)
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    gate: Mapped[str | None] = mapped_column(String(20), nullable=True)  # AtD / AtO requests
    subject_id: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )  # e.g. OCET version id
    subject_label: Mapped[str] = mapped_column(
        Text, default=""
    )  # card summary, e.g. "OCET v2 · 5-yr 1.9M"
    status: Mapped[str] = mapped_column(
        String(12), default="Pending"
    )  # Pending | Approved | Rejected | Cancelled
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_source: Mapped[str] = mapped_column(String(20), default="Human")  # actor type
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    steps: Mapped[list[ApprovalStep]] = relationship(
        back_populates="request",
        order_by="ApprovalStep.step",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ApprovalStep(TimestampMixin, Base):
    __tablename__ = "approval_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("approval_requests.id"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))  # PLANNER | OLM | IRM | ARCHITECT | CISO_BISO
    label: Mapped[str] = mapped_column(String(120), default="")
    approver_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(12), default="Waiting"
    )  # Waiting | Pending | Approved | Rejected | Cancelled
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # when it became Pending
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped[ApprovalRequest] = relationship(back_populates="steps")
