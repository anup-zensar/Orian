"""Playbook library (spec §6 PlaybookItem, EvalTarget). Loaded from seed; edited in Admin."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class PlaybookItem(TimestampMixin, Base):
    """One library line. ``source``: FRAMEWORK | AI_PLAYBOOK | PORTFOLIO | COMMON."""

    __tablename__ = "playbook_items"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # FW-001, S45-014, GCC-01, ALL-01
    source: Mapped[str] = mapped_column(String(20), index=True)
    source_label: Mapped[str] = mapped_column(
        String(80), default=""
    )  # e.g. "AI Playbook Checklist v3.0"
    portfolio: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    gate: Mapped[str] = mapped_column(String(20))  # gate code, e.g. SG4_ATD
    lens: Mapped[str] = mapped_column(String(20))  # Business | Technical | Compliance
    secondary_lens: Mapped[str] = mapped_column(String(20), default="")
    lens_is_suggested: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(120), default="")  # FW category / AI section
    kind: Mapped[str] = mapped_column(
        String(30), default="Deliverable"
    )  # Check|Question|KPI|Evidence|Support model|Deliverable
    applicable_tiers: Mapped[list[int]] = mapped_column(JSON, default=list)
    tier_label: Mapped[str] = mapped_column(String(40), default="")
    tier_unspecified: Mapped[bool] = mapped_column(Boolean, default=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    mandatory_rule: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # always | if_applicable
    applies_to_project_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    owner_role_hint: Mapped[str] = mapped_column(Text, default="")
    automation_tag: Mapped[str] = mapped_column(String(60), default="")
    phase_window: Mapped[str] = mapped_column(String(40), default="")
    source_sheet: Mapped[str] = mapped_column(String(80), default="")
    source_cell: Mapped[str] = mapped_column(String(20), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    is_compliance_control: Mapped[bool] = mapped_column(Boolean, default=False)
    linked_module: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # OCET | SUPPORT_MODEL
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class EvalTarget(TimestampMixin, Base):
    """Eval-metric target per tier (eval_metrics.json -> targets_by_tier), editable in Admin."""

    __tablename__ = "eval_targets"
    __table_args__ = (UniqueConstraint("metric_id", "tier"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_id: Mapped[str] = mapped_column(String(10), index=True)  # EV-01
    metric: Mapped[str] = mapped_column(String(120))
    tier: Mapped[int] = mapped_column(Integer)
    target_text: Mapped[str] = mapped_column(String(200))
    operator: Mapped[str | None] = mapped_column(String(8), nullable=True)  # >= <= < > == abs<=
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    evaluation: Mapped[str] = mapped_column(String(10), default="manual")  # auto | manual
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)  # tier_targets_confirmed
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
