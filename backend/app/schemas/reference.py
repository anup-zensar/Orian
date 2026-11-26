"""GET /api/v1/reference payload (spec §9: gates, lenses, statuses, options, tiers, questions, rag rule,
roles, ocet config) – everything the UI needs for forms, chips and labels.

CR-01: every existing key keeps its shape (additive changes only, tests/test_config_reference_compat.py).
New keys: ``lists`` (all option lists), ``intake_fields``, ``checklists``, ``thresholds``,
``approval_chain_labels``; ``project_types``, ``portfolio_details``, ``roles`` and
``approval_chains`` gain fields. Inactive values are left out unless the request has
``?include_inactive=true`` (the UI's reference query does, and filters on ``active`` itself)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class GateOut(BaseModel):
    code: str
    order: int
    label: str
    short: str
    type: str  # stage_review | decision | closure
    description: str = ""


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
    # CR-01 (design 1.1): behaviour flags and display
    label: str = ""
    description: str = ""
    active: bool = True
    sort_order: int = 0
    has_ai_profile: bool = False
    has_eval_metrics: bool = False
    required_intake_fields: list[str] = []
    synonyms: list[str] = []


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
    # CR-01 (design 1.4)
    label: str = ""
    description: str = ""
    requires_sites: bool = False
    sites_label: str = ""
    synonyms: list[str] = []
    active: bool = True
    sort_order: int = 0


class IntakeOptionsOut(BaseModel):
    """Active VALUES of the intake option lists. The six below always exist; further lists of the
    "Intake" group are added as extra keys (``dict[str, list[str]]``, design 4)."""

    model_config = ConfigDict(extra="allow")

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
    is_mock: bool = False  # CR-01: a mocked step (e.g. CISO/BISO, acted for by IRM in demo mode)


class RoleOut(BaseModel):
    code: str
    label: str
    # CR-01 (design 1.6)
    short_label: str = ""
    phrase_label: str = ""
    active: bool = True
    is_builtin: bool = True
    has_transition_slot: bool = False
    transition_column: str | None = None
    can_approve: bool = False
    sort_order: int = 0


class OptionOut(BaseModel):
    """One item of an option list (``ReferenceOut.lists[key]``)."""

    value: str
    label: str
    description: str = ""
    meta: dict[str, Any] = {}
    active: bool = True


class IntakeFieldRefOut(BaseModel):
    """One intake form field (design 1.5). ``option_list``: list key for select / multiselect (the
    virtual lists ``project_types`` and ``portfolios`` come from their own keys); for type ``user``
    the role code whose users are offered."""

    key: str
    label: str
    help: str = ""
    builtin: bool = False
    structural: bool = False
    type: str
    option_list: str | None = None
    visible: bool = True
    required_mode: str = "never"
    required_for_project_types: list[str] = []
    applies_to_project_types: list[str] = []
    applies_to_portfolios: list[str] = []
    section: str = ""
    sort_order: int = 0
    show_on_overview: bool = False
    show_in_list: bool = False
    filterable: bool = False
    form: str = "intake"
    min: float | None = None
    max: float | None = None
    max_length: int | None = None
    active: bool = True


class ChecklistRefOut(BaseModel):
    code: str
    label: str
    description: str = ""
    kind: str  # library | portfolio_golden | common
    tier_filtered: bool = False
    is_builtin: bool = False
    active: bool = True
    sort_order: int = 0


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
    # --- CR-01 additions (design 4) ---
    lists: dict[str, list[OptionOut]] = {}
    intake_fields: list[IntakeFieldRefOut] = []
    checklists: list[ChecklistRefOut] = []
    thresholds: dict[str, Any] = (
        {}
    )  # display subset: rag, insights, calendar_horizon_days, default_tier ...
    approval_chain_labels: dict[str, str] = {}
