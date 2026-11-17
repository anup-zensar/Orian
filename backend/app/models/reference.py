"""Reference and configuration tables (spec §6 User, FlavourRule, Portfolio; Admin-editable config)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # "U01"
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[str] = mapped_column(String(20))  # app.permissions.Role
    focal_label: Mapped[str | None] = mapped_column(String(60), nullable=True)


class ReferenceData(TimestampMixin, Base):
    """Read-mostly reference blobs loaded from seed (e.g. key="reference" = reference.json)."""

    __tablename__ = "reference_data"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    data: Mapped[Any] = mapped_column(JSON)


class AppSetting(TimestampMixin, Base):
    """Small key/value store (e.g. "today_override", "last_reminder_run")."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=True)


class FlavourRule(TimestampMixin, Base):
    """Project type -> checklists (reference.json -> project_types); editable in Admin (FR-100)."""

    __tablename__ = "flavour_rules"

    project_type: Mapped[str] = mapped_column(String(40), primary_key=True)
    checklists: Mapped[list[str]] = mapped_column(JSON)  # ["FRAMEWORK", "AI_PLAYBOOK"]
    requires_tiering: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Portfolio(TimestampMixin, Base):
    __tablename__ = "portfolios"

    name: Mapped[str] = mapped_column(String(60), primary_key=True)  # "GCC"
    code: Mapped[str] = mapped_column(String(10))
    focus_areas: Mapped[list[str]] = mapped_column(JSON)
    intake_extra_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)


class ApprovalChainConfig(TimestampMixin, Base):
    """reference.json -> approval_chains; editable in Admin. steps = [{step, role, label}]."""

    __tablename__ = "approval_chain_configs"

    type: Mapped[str] = mapped_column(
        String(30), primary_key=True
    )  # OCET | AtD | AtO | SUPPORT_MODEL | EXCEPTION
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class ReminderRule(TimestampMixin, Base):
    """Reminder engine rules R1–R7 (BR-060) with editable thresholds (FR-100)."""

    __tablename__ = "reminder_rules"

    id: Mapped[str] = mapped_column(String(4), primary_key=True)  # "R1"
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    autonomous_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    params: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict
    )  # e.g. {"days_before_decision": 14}
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
