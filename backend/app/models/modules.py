"""OCET and support model modules (spec §6 OcetEstimate/OcetVersion/OcetLine, SupportModel)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin


class OcetEstimate(TimestampMixin, Base):
    __tablename__ = "ocet_estimates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), unique=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    start_year: Mapped[int] = mapped_column(Integer)
    horizon_years: Mapped[int] = mapped_column(Integer, default=5)
    current_version: Mapped[int] = mapped_column(Integer, default=1)

    versions: Mapped[list[OcetVersion]] = relationship(
        back_populates="estimate", order_by="OcetVersion.version", lazy="selectin"
    )


class OcetVersion(TimestampMixin, Base):
    __tablename__ = "ocet_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("ocet_estimates.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    # Draft | Inputs pending | Submitted | Planner approved | Approved | Rejected | Superseded
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("approval_requests.id"), nullable=True
    )

    estimate: Mapped[OcetEstimate] = relationship(back_populates="versions")
    lines: Mapped[list[OcetLine]] = relationship(
        back_populates="version",
        order_by="OcetLine.sort_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class OcetLine(TimestampMixin, Base):
    __tablename__ = "ocet_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("ocet_versions.id"), index=True)
    line_key: Mapped[str] = mapped_column(String(10))  # "L1" – stable across versions (variance)
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text, default="")
    vendor: Mapped[str] = mapped_column(String(120), default="")
    pricing_basis: Mapped[str] = mapped_column(String(40), default="Fixed (contract)")
    base_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    growth_pct: Mapped[float] = mapped_column(Float, default=0.0)
    year_overrides: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)  # {"2028": 30}
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_owner_role: Mapped[str] = mapped_column(String(20), default="PM")
    input_owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    input_status: Mapped[str] = mapped_column(
        String(12), default="Provided"
    )  # Provided | Requested | Missing
    input_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # R5
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    version: Mapped[OcetVersion] = relationship(back_populates="lines")


class SupportModel(TimestampMixin, Base):
    __tablename__ = "support_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transition_id: Mapped[str] = mapped_column(ForeignKey("transitions.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="Draft")  # Draft | In review | Agreed
    inputs: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict
    )  # {confluence_url, confluence, files[]}
    landscape: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # spec §8.8 schema
    generated_pptx_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pptx_version: Mapped[int] = mapped_column(Integer, default=0)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    approval_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("approval_requests.id"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
