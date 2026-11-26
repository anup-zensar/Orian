"""Transitions and their checklist (spec §6 Transition, TierAssessment, AIProfile, TransitionItem)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin
from app.models.playbook import PlaybookItem


class Transition(TimestampMixin, Base):
    __tablename__ = "transitions"

    id: Mapped[str] = mapped_column(String(10), primary_key=True)  # TR-0001
    name: Mapped[str] = mapped_column(String(200))
    servicenow_project_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    portfolio: Mapped[str] = mapped_column(String(60), index=True)
    region: Mapped[str] = mapped_column(String(60), index=True)
    market: Mapped[str] = mapped_column(String(120), default="")
    project_type: Mapped[str] = mapped_column(
        String(40)
    )  # Normal | Infrastructure | Agentic AI (config project_types; labels differ)
    investment_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivery_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    audience: Mapped[str | None] = mapped_column(String(40), nullable=True)
    write_actions: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sensitive_data: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_gate: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # intake option label
    current_gate: Mapped[str] = mapped_column(String(20), default="SG0")  # gate code
    risk_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tier_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # Proposed | Confirmed
    or_focal_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    pm_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    architect_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    olm_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    irm_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    next_decision_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    autonomous_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="Active")  # Active | Closed
    sites: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list
    )  # Retail only: [{site_id, site_key}]
    blocker_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_flagship: Mapped[bool] = mapped_column(Boolean, default=False)
    # additions (PLAN.md): assessment launched from the Scope page (FR-022); hypercare "no defects" (FR-036)
    assessment_launched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hypercare_no_defects_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    # M3: playbook item id -> {"applies": "Yes"|"No"|"To confirm", "reason": str|None}, decided on the
    # Scope page before launch (applied to TransitionItem.applicability at launch)
    scope_decisions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # CR-01: values of admin-defined intake fields {key: value}. NULL = none.
    custom_fields: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class TierAssessment(TimestampMixin, Base):
    __tablename__ = "tier_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), unique=True)
    answers: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict)  # {"TQ1": false, ...}
    proposed_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rationale: Mapped[list[str]] = mapped_column(JSON, default=list)
    proposed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed_by_or_focal: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_by_irm: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    change_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # IRM "Change tier" reason


class AIProfile(TimestampMixin, Base):
    """AI profile questionnaire (AI Transition = Agentic AI only), spec §6 / §8.5 step 3."""

    __tablename__ = "ai_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), unique=True)
    infrastructure_solution: Mapped[str] = mapped_column(Text, default="")
    agentic_framework: Mapped[str] = mapped_column(Text, default="")
    multi_agent_orchestration: Mapped[bool] = mapped_column(Boolean, default=False)
    number_of_users: Mapped[str] = mapped_column(String(60), default="")
    agentic_workflows: Mapped[str] = mapped_column(Text, default="")
    models_used: Mapped[str] = mapped_column(Text, default="")
    data_sources: Mapped[str] = mapped_column(Text, default="")
    hosting: Mapped[str] = mapped_column(Text, default="")
    write_actions_detail: Mapped[str] = mapped_column(Text, default="")
    # CR-01: values of admin-defined AI-profile fields {key: value}
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class TransitionItem(TimestampMixin, Base):
    """One applicable (or tier-excluded) library line for one transition (BR-010)."""

    __tablename__ = "transition_items"
    __table_args__ = (UniqueConstraint("transition_id", "playbook_item_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    playbook_item_id: Mapped[str] = mapped_column(ForeignKey("playbook_items.id"))
    applicability: Mapped[str] = mapped_column(
        String(20), default="Applies"
    )  # Applies | Not applicable | To confirm
    na_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    excluded_by: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # tier | project_type | portfolio
    status: Mapped[str] = mapped_column(String(40), default="Not started")
    gap_severity: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # Critical | Major | Minor
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_gate: Mapped[str] = mapped_column(String(20))
    design_effectiveness: Mapped[str | None] = mapped_column(
        String(4), nullable=True
    )  # – | Yes | No | N/A
    note: Mapped[str] = mapped_column(Text, default="")
    linked_module: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # OCET | SUPPORT_MODEL
    last_updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Human | Workflow rule | System (Orion agent never sets status – BR-050)
    last_updated_source: Mapped[str] = mapped_column(String(20), default="System")

    playbook_item: Mapped[PlaybookItem] = relationship(lazy="joined")
