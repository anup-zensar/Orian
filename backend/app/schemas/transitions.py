"""Transition list / register DTOs (spec §8.2 register columns, §8.3, §9 GET /transitions)."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import LensValues, PersonRef


class TransitionSummaryOut(BaseModel):
    """One register row. Readiness, gaps and RAG are computed live (BR-020, BR-021) – never stored."""

    id: str
    name: str
    portfolio: str
    region: str
    market: str
    servicenow_project_id: str | None = None  # ServiceNow project number, e.g. PRJ0041037
    custom_fields: dict[str, Any] = (
        {}
    )  # "Additional details" values; the list shows those flagged show_in_list
    project_type: str
    current_gate: str  # gate code, e.g. SG4_ATD
    current_gate_short: str  # e.g. AtD
    current_gate_type: str  # stage_review | decision | closure
    risk_tier: int | None
    tier_status: str | None  # Proposed | Confirmed
    status: str  # Active | Closed
    is_flagship: bool
    autonomous_mode: bool
    assessment_launched: bool  # False until "Launch readiness assessment" (FR-022)
    or_focal: PersonRef
    next_decision_date: date | None
    days_to_next_decision: int | None  # negative when the date has passed
    lens_readiness: LensValues  # readiness % per lens at the current gate
    overall_readiness: int
    open_gaps: int
    critical_gaps: int
    rag: str  # Red | Amber | Green | Grey (not started, A-34)
    blocker_note: str | None


class TransitionFilters(BaseModel):
    """Query filters shared by GET /transitions and GET /control-tower (spec §8.2: filters reflected in
    the URL). Every filter is optional; all given filters must match (AND)."""

    portfolio: str | None = None
    region: str | None = None
    gate: str | None = Field(default=None, description="Current gate code, e.g. SG4_ATD")
    rag: str | None = Field(default=None, description="Red | Amber | Green | Grey")
    type: str | None = Field(default=None, description="Project type, e.g. Agentic AI")
    q: str | None = Field(
        default=None,
        description="Case-insensitive search in transition id, name, market, ServiceNow project ID and OR focal name",
    )
    decision_within_days: int | None = Field(
        default=None, ge=0, description="Next decision date between today and today + N days"
    )
    has_critical: bool | None = Field(default=None, description="At least one open critical gap")
    compliance_below: int | None = Field(
        default=None, ge=0, le=101, description="Compliance readiness strictly below N %"
    )
    mine: bool | None = Field(
        default=None,
        description="Only transitions where the current user is OR focal, PM, Architect, OLM or IRM "
        "(Planner, Leadership and Admin: all transitions)",
    )
    status: str | None = Field(default=None, description="Active | Closed")
