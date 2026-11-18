"""Intake and transition detail DTOs (spec §8.4, §8.7 header, §9 Transitions)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import LensValues, PersonRef


class SiteIn(BaseModel):
    site_id: str = Field(default="", max_length=100)
    site_key: str = Field(default="", max_length=100)


class ServiceNowProjectOut(BaseModel):
    """Prefill for the intake form (mock lookup)."""

    project_id: str
    name: str
    project_type: str | None = None
    investment_type: str | None = None
    delivery_method: str | None = None
    portfolio: str | None = None
    region: str | None = None
    market: str | None = None
    description: str = ""
    pm_name: str | None = None
    pm_user_id: str | None = None  # resolved from the PM name, None when no user matches


class TransitionCreateIn(BaseModel):
    confirm_duplicate: bool = Field(
        default=False,
        description="Create even though an active transition already has this ServiceNow project id",
    )
    name: str = Field(min_length=1, max_length=200)
    servicenow_project_id: str | None = Field(default=None, max_length=50)
    project_type: str = Field(max_length=100)
    portfolio: str = Field(max_length=100)
    region: str = Field(max_length=100)
    market: str = Field(default="", max_length=200)
    sites: list[SiteIn] = Field(default_factory=list, max_length=500)
    audience: str | None = Field(default=None, max_length=100)
    write_actions: str | None = Field(default=None, max_length=100)
    sensitive_data: str | None = Field(default=None, max_length=100)
    target_gate: str | None = Field(default=None, max_length=50)
    investment_type: str | None = Field(default=None, max_length=100)
    delivery_method: str | None = Field(default=None, max_length=100)
    description: str = Field(default="", max_length=4000)
    # Optional for an OR focal (defaults to themselves); PM / Admin must pick one (validated in the domain).
    or_focal_user_id: str | None = Field(default=None, max_length=20)
    pm_user_id: str | None = Field(default=None, max_length=20)
    architect_user_id: str | None = Field(default=None, max_length=20)
    olm_user_id: str | None = Field(default=None, max_length=20)
    irm_user_id: str | None = Field(default=None, max_length=20)
    next_decision_date: date | None = None


class TransitionUpdateIn(BaseModel):
    """PATCH: every field optional; only fields sent are changed (``model_fields_set``)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    servicenow_project_id: str | None = Field(default=None, max_length=50)
    project_type: str | None = Field(default=None, max_length=100)
    portfolio: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    market: str | None = Field(default=None, max_length=200)
    sites: list[SiteIn] | None = Field(default=None, max_length=500)
    audience: str | None = Field(default=None, max_length=100)
    write_actions: str | None = Field(default=None, max_length=100)
    sensitive_data: str | None = Field(default=None, max_length=100)
    target_gate: str | None = Field(default=None, max_length=50)
    investment_type: str | None = Field(default=None, max_length=100)
    delivery_method: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    or_focal_user_id: str | None = Field(default=None, max_length=20)
    pm_user_id: str | None = Field(default=None, max_length=20)
    architect_user_id: str | None = Field(default=None, max_length=20)
    olm_user_id: str | None = Field(default=None, max_length=20)
    irm_user_id: str | None = Field(default=None, max_length=20)
    next_decision_date: date | None = None
    blocker_note: str | None = Field(default=None, max_length=4000)


class AutonomousModeIn(BaseModel):
    enabled: bool


class SiteOut(BaseModel):
    site_id: str
    site_key: str


class RolesOut(BaseModel):
    or_focal: PersonRef | None
    pm: PersonRef | None
    architect: PersonRef | None
    olm: PersonRef | None
    irm: PersonRef | None


class TierInfoOut(BaseModel):
    proposed_tier: int | None
    confirmed_tier: int | None
    status: str | None  # Proposed | Confirmed
    rationale: list[str]
    proposed_by: PersonRef | None
    confirmed_by_or_focal: PersonRef | None
    confirmed_by_irm: PersonRef | None
    confirmed_at: datetime | None
    change_reason: str | None
    answers: dict[str, bool] = {}  # tiering questions TQ1..TQ5 saved so far


class ItemCountsOut(BaseModel):
    framework: int
    ai_applicable: int
    ai_excluded: int
    golden_set_applies: int
    golden_set_to_confirm: int
    common: int
    total: int


class LensCardOut(BaseModel):
    """Overview lens card at the current gate (spec §8.7)."""

    lens: str  # Business | Technical | Compliance
    question: str
    owner_label: str
    scope: int  # applicable items at the gate
    done: int
    in_progress: int
    not_started: int
    open_gaps: int
    critical_gaps: int
    readiness_pct: int


class GateStepOut(BaseModel):
    code: str
    short: str
    label: str
    type: str  # stage_review | decision | closure
    state: str  # done | current | upcoming


class TransitionDetailOut(BaseModel):
    # --- every TransitionSummaryOut field ---
    id: str
    name: str
    portfolio: str
    region: str
    market: str
    project_type: str
    current_gate: str
    current_gate_short: str
    current_gate_type: str
    risk_tier: int | None
    tier_status: str | None
    status: str
    is_flagship: bool
    autonomous_mode: bool
    assessment_launched: bool
    or_focal: PersonRef
    next_decision_date: date | None
    days_to_next_decision: int | None
    lens_readiness: LensValues
    overall_readiness: int
    open_gaps: int
    critical_gaps: int
    rag: str
    blocker_note: str | None
    # --- detail ---
    servicenow_project_id: str | None
    description: str
    investment_type: str | None
    delivery_method: str | None
    audience: str | None
    write_actions: str | None
    sensitive_data: str | None
    target_gate: str | None
    sites: list[SiteOut]
    roles: RolesOut
    flavour_label: str  # e.g. "Agentic AI · GCC · Global"
    requires_tiering: bool
    tier: TierInfoOut | None
    checklist_banner: str | None  # "Checklist based on proposed Tier 2 — confirm tier to finalise"
    item_counts: ItemCountsOut | None  # None before launch
    lenses: list[LensCardOut]
    gates: list[GateStepOut]
    hypercare_no_defects_confirmed: bool
    created_at: datetime | None
    created_by: PersonRef | None
    # What the CURRENT user may do on this transition (BE#1, spec 12): permission code (e.g.
    # "record_gate_decision") -> None when allowed, else the reason to show on the disabled control.
    # Covers every transition-scoped permission (app.access.TRANSITION_PERMS).
    access: dict[str, str | None] = {}
