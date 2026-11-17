"""GET /api/v1/reference payload (spec §9: gates, lenses, statuses, options, tiers, questions, rag rule,
roles, ocet config) – everything the UI needs for forms, chips and labels."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GateOut(BaseModel):
    code: str
    order: int
    label: str
    short: str
    type: str  # stage_review | decision | closure


class LensOut(BaseModel):
    code: str
    question: str
    owner_roles: list[str]
    signoff_role: str
    color_hint: str


class ProjectTypeOut(BaseModel):
    code: str
    checklists: list[str]
    requires_tiering: bool
    note: str | None = None


class IntakeExtraFieldOut(BaseModel):
    key: str
    label: str
    type: str
    required: bool
    fields: list[dict[str, Any]] = []


class PortfolioDetailOut(BaseModel):
    name: str
    code: str
    focus_areas: list[str]
    intake_extra_fields: list[IntakeExtraFieldOut]
    golden_set_count: int
    golden_set_mandatory_count: int


class IntakeOptionsOut(BaseModel):
    audience: list[str]
    write_actions: list[str]
    sensitive_data: list[str]
    target_gate: list[str]
    investment_type: list[str]
    delivery_method: list[str]


class TierOut(BaseModel):
    tier: int
    name: str
    definition: str
    examples: str
    builder_persona: str


class TierQuestionOut(BaseModel):
    id: str
    text: str
    if_yes: str


class ApprovalChainStepOut(BaseModel):
    step: int
    role: str
    label: str


class RoleOut(BaseModel):
    code: str
    label: str


class ChecklistCountsOut(BaseModel):
    """Active library sizes for the intake "Auto-scope" preview (spec §8.4)."""

    framework: int
    ai_playbook_total: int
    ai_playbook_by_tier: dict[str, int]  # tier ("1".."4") -> applicable items
    common: int


class EnumsOut(BaseModel):
    """Small vocabularies used by forms and filters."""

    severities: list[str]
    evidence_types: list[str]
    evidence_statuses: list[str]
    action_statuses: list[str]
    action_priorities: list[str]
    condition_statuses: list[str]
    exception_statuses: list[str]
    risk_ratings: list[str]
    defect_priorities: list[str]
    defect_statuses: list[str]
    actor_types: list[str]
    draft_kinds: list[str]
    approval_types: list[str]
    applicability: list[str]
    item_sources: list[str]


class AppInfoOut(BaseModel):
    demo_mode: bool
    ai_mode: str
    mail_mode: str
    orion_mailbox: str


class ReferenceOut(BaseModel):
    gates: list[GateOut]
    gate_outcomes: dict[str, list[str]]
    lenses: list[LensOut]
    item_statuses: dict[str, list[str]]
    done_statuses: list[str]
    na_statuses: list[str]
    gap_statuses: list[str]
    design_effectiveness_options: list[str]
    project_types: list[ProjectTypeOut]
    flavour_rule_note: str
    portfolios: list[str]
    portfolio_details: list[PortfolioDetailOut]
    regions: list[str]
    intake_options: IntakeOptionsOut
    tiers: list[TierOut]
    tier_dimensions: list[str]
    tier_questions: list[TierQuestionOut]
    rag_rule: dict[str, str]
    approval_chains: dict[str, list[ApprovalChainStepOut]]
    risk_acceptance_routes: list[dict[str, str]]
    risk_acceptance_then: list[str]
    ocet: dict[str, Any]
    roles: list[RoleOut]
    checklist_counts: ChecklistCountsOut
    enums: EnumsOut
    app: AppInfoOut
