"""CR-01 no-code configuration: every admin DTO (design 4). Contract of ``routers/config_admin.py``.

Conventions
-----------
* Codes / keys are immutable: they appear in ``*CreateIn`` and in the path, never in ``*UpdateIn``;
  labels are editable.
* ``used_by`` = number of transitions (or records) that use the value; ``DELETE`` answers 409
  "Used by N transitions - deactivate instead".
* A write returns the saved section (the same shape as the GET), so the UI needs no re-fetch.
* ``*UpdateIn`` bodies are PATCH bodies: omitted fields stay unchanged.
* Validation problems are a 422 with one ``reasons[]`` entry per problem (guardrails, design 5).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.admin import PlaybookItemAdminOut

NOTICE_NEW_ONLY = "Changes affect NEW transitions; existing transitions keep their items."
NOTICE_LIVE = "Applies immediately; RAG recalculates for all active transitions."

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Text80 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
Text200 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
LongText = Annotated[str, StringConstraints(max_length=4000)]
FieldType = Literal[
    "text", "textarea", "number", "date", "select", "multiselect", "boolean", "user"
]
RequiredMode = Literal["never", "always", "by_project_type"]
ChecklistKind = Literal["library", "portfolio_golden", "common"]
FieldForm = Literal["intake", "ai_profile"]
Scope = Literal["global", "transition"]


# --------------------------------------------------------------------------- project types (1.1)


class ProjectTypeAdminOut(BaseModel):
    code: str
    label: str
    description: str = ""
    active: bool = True
    sort_order: int = 0
    checklists: list[str]
    requires_tiering: bool
    has_ai_profile: bool
    has_eval_metrics: bool
    required_intake_fields: list[str] = []
    synonyms: list[str] = []
    color: str | None = None
    note: str | None = None
    used_by: int = 0
    notice: str = NOTICE_NEW_ONLY


class ProjectTypeCreateIn(BaseModel):
    """POST /admin/project-types. ``code`` is immutable (letters, digits, space, - _ & /)."""

    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=40)]
    label: Text80 = ""
    description: LongText = ""
    checklists: list[Code] = Field(default_factory=list, max_length=30)
    requires_tiering: bool = False
    has_ai_profile: bool = False
    has_eval_metrics: bool = False
    required_intake_fields: list[Code] = Field(default_factory=list, max_length=40)
    synonyms: list[Text80] = Field(default_factory=list, max_length=30)
    color: Text80 | None = None
    note: LongText | None = None


class ProjectTypeUpdateIn(BaseModel):
    label: Text80 | None = None
    description: LongText | None = None
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    checklists: list[Code] | None = Field(default=None, max_length=30)
    requires_tiering: bool | None = None
    has_ai_profile: bool | None = None
    has_eval_metrics: bool | None = None
    required_intake_fields: list[Code] | None = Field(default=None, max_length=40)
    synonyms: list[Text80] | None = Field(default=None, max_length=30)
    color: Text80 | None = None
    note: LongText | None = None


class ProjectTypePreviewOut(BaseModel):
    """GET /admin/project-types/{code}/preview: what a NEW transition of this type would get."""

    code: str
    items_by_gate: dict[str, int]  # gate code -> number of active library items
    items_by_checklist: dict[str, int]  # checklist code -> items (portfolio golden set excluded)
    total_items: int
    shows_tiering: bool
    shows_ai_profile: bool
    shows_eval_metrics: bool
    required_intake_fields: list[str]
    notes: list[str] = []


# --------------------------------------------------------------------------- checklists (1.2)


class ChecklistAdminOut(BaseModel):
    code: str
    label: str
    description: str = ""
    kind: ChecklistKind
    tier_filtered: bool
    is_builtin: bool
    active: bool
    sort_order: int
    item_count: int = 0
    project_types: list[str] = []  # project types that list this checklist
    notice: str = NOTICE_NEW_ONLY


class ChecklistCreateIn(BaseModel):
    """POST /admin/checklists. New checklists are ``library`` checklists (included when a project
    type lists them); ``kind`` of a built-in cannot change."""

    code: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Z][A-Z0-9_]{1,39}$")
    ]
    label: Text80
    description: LongText = ""
    tier_filtered: bool = False


class ChecklistUpdateIn(BaseModel):
    label: Text80 | None = None
    description: LongText | None = None
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    tier_filtered: bool | None = None


class PlaybookItemCreateIn(BaseModel):
    """POST /admin/playbook-items: a new library item in ANY checklist (``source`` = checklist code).
    ``id`` is generated from the checklist code when omitted (e.g. SECURITY_PLAYBOOK-001)."""

    id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    source: Code
    portfolio: Text80 | None = None  # required for a portfolio_golden checklist
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    description: LongText = ""
    detail: LongText = ""
    gate: Annotated[str, StringConstraints(max_length=20)]  # gate code
    lens: Literal["Business", "Technical", "Compliance"]
    secondary_lens: str = ""
    category: Text200 = ""
    kind: Text80 = "Deliverable"
    applicable_tiers: list[int] = Field(default_factory=list, max_length=8)
    mandatory: bool = True
    mandatory_rule: Literal["always", "if_applicable"] | None = "always"
    applies_to_project_types: list[Code] = Field(default_factory=list, max_length=30)  # [] = all
    owner_role_hint: Text200 = ""
    default_owner_role: Code | None = None  # a role code
    linked_module: Literal["OCET", "SUPPORT_MODEL"] | None = None


PlaybookItemCreateOut = PlaybookItemAdminOut


# --------------------------------------------------------------------------- portfolios (1.4)


class PortfolioAdminOut(BaseModel):
    name: str
    code: str
    label: str
    description: str = ""
    focus_areas: list[str] = []
    active: bool = True
    sort_order: int = 0
    requires_sites: bool = False
    sites_label: str = ""
    synonyms: list[str] = []
    golden_set_count: int = 0
    used_by: int = 0
    notice: str = NOTICE_NEW_ONLY


class PortfolioCreateIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]
    label: Text80 = ""
    description: LongText = ""
    focus_areas: list[Text200] = Field(default_factory=list, max_length=30)
    requires_sites: bool = False
    sites_label: Text80 = ""
    synonyms: list[Text80] = Field(default_factory=list, max_length=30)


class PortfolioUpdateIn(BaseModel):
    code: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)] | None
    ) = None
    label: Text80 | None = None
    description: LongText | None = None
    focus_areas: list[Text200] | None = Field(default=None, max_length=30)
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    requires_sites: bool | None = None
    sites_label: Text80 | None = None
    synonyms: list[Text80] | None = Field(default=None, max_length=30)


# --------------------------------------------------------------------------- option lists (1.3)


class MetaFieldOut(BaseModel):
    """A declared meta key of a list: tells the editor which extra columns to show."""

    key: str
    type: str  # token | text | number | boolean | select | list | role | gate
    label: str = ""
    options: list[str] = []


class MetaFieldIn(BaseModel):
    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
    type: Literal["token", "text", "number", "boolean", "select", "list", "role", "gate"]
    label: Text80 = ""
    options: list[Text80] = Field(default_factory=list, max_length=40)


class OptionListAdminOut(BaseModel):
    key: str
    label: str
    description: str = ""
    group: str = ""
    is_builtin: bool
    structural: bool  # label / description only; add, delete and recode are refused
    lock_reason: str | None = None  # why it is locked (shown beside the lock icon)
    meta_fields: list[MetaFieldOut] = []
    item_count: int = 0
    active_count: int = 0
    sort_order: int = 0


class OptionListCreateIn(BaseModel):
    """POST /admin/option-lists: a custom list (used by custom fields of type select / multiselect)."""

    key: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    label: Text80
    description: LongText = ""
    group: Text80 = "Custom lists"
    meta_fields: list[MetaFieldIn] = Field(default_factory=list, max_length=10)


class OptionListUpdateIn(BaseModel):
    label: Text80 | None = None
    description: LongText | None = None
    group: Text80 | None = None
    meta_fields: list[MetaFieldIn] | None = Field(default=None, max_length=10)


class OptionItemOut(BaseModel):
    value: str
    label: str
    description: str = ""
    meta: dict[str, Any] = {}
    active: bool = True
    sort_order: int = 0
    used_by: int = 0


class OptionItemIn(BaseModel):
    """One row of the PUT body. ``value`` identifies an existing row (it never changes); a new
    ``value`` adds a row. A row missing from the PUT is DEACTIVATED when used, removed otherwise."""

    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)] = ""
    description: LongText = ""
    meta: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class OptionItemsIn(BaseModel):
    """PUT /admin/option-lists/{key}/items: replaces the ORDERED items (position = sort_order)."""

    items: list[OptionItemIn] = Field(max_length=500)


class OptionItemsOut(BaseModel):
    option_list: OptionListAdminOut
    items: list[OptionItemOut]
    notice: str = NOTICE_LIVE


class ConfigResetIn(BaseModel):
    """POST /admin/config/reset (extension of design 4): restore ONE editor to seed/config.json.
    Refused (409) when it would remove a value that is in use. ``key`` selects a list / role / ...
    """

    section: Literal[
        "option_list",
        "intake_fields",
        "roles",
        "permissions",
        "tiering",
        "thresholds",
        "labels",
        "gates",
        "lenses",
        "message_templates",
    ]
    key: str | None = None


class ConfigResetOut(BaseModel):
    section: str
    key: str | None = None
    restored: int  # rows restored
    notice: str = ""


# --------------------------------------------------------------------------- intake fields (1.5)


class IntakeFieldAdminOut(BaseModel):
    key: str
    label: str
    help: str = ""
    builtin: bool
    structural: bool
    type: FieldType
    option_list: str | None = None
    visible: bool = True
    required_mode: RequiredMode = "never"
    required_for_project_types: list[str] = []
    applies_to_project_types: list[str] = []
    applies_to_portfolios: list[str] = []
    section: str = ""
    sort_order: int = 0
    show_on_overview: bool = False
    filterable: bool = False
    form: FieldForm = "intake"
    min: float | None = None
    max: float | None = None
    max_length: int | None = None
    active: bool = True
    used_by: int = 0  # transitions holding a value (custom fields) / using the field
    type_locked: bool = False  # True once any transition holds a value
    lock_reason: str | None = None


class IntakeFieldCreateIn(BaseModel):
    """POST /admin/intake-fields: a custom field. ``key`` is generated from the label as
    ``cf_<slug>`` (``^[a-z][a-z0-9_]{1,40}$``) unless given."""

    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    key: Annotated[str, StringConstraints(pattern=r"^cf_[a-z][a-z0-9_]{1,40}$")] | None = None
    type: FieldType = "text"
    option_list: Text80 | None = None  # select / multiselect: an option list key
    help: LongText = ""
    required_mode: RequiredMode = "never"
    required_for_project_types: list[Code] = Field(default_factory=list, max_length=30)
    applies_to_project_types: list[Code] = Field(default_factory=list, max_length=30)
    applies_to_portfolios: list[Text80] = Field(default_factory=list, max_length=30)
    section: Text80 = "Additional details"
    show_on_overview: bool = False
    filterable: bool = False
    form: FieldForm = "intake"
    min: float | None = None
    max: float | None = None
    max_length: int | None = Field(default=None, ge=1, le=10000)


class IntakeFieldUpdateIn(BaseModel):
    """PATCH: label stays editable on every field; structural fields refuse hide / optional /
    deactivate; ``type`` is refused once a transition holds a value."""

    label: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
        | None
    ) = None
    help: LongText | None = None
    type: FieldType | None = None
    option_list: Text80 | None = None
    visible: bool | None = None
    required_mode: RequiredMode | None = None
    required_for_project_types: list[Code] | None = Field(default=None, max_length=30)
    applies_to_project_types: list[Code] | None = Field(default=None, max_length=30)
    applies_to_portfolios: list[Text80] | None = Field(default=None, max_length=30)
    section: Text80 | None = None
    show_on_overview: bool | None = None
    filterable: bool | None = None
    min: float | None = None
    max: float | None = None
    max_length: int | None = Field(default=None, ge=1, le=10000)
    active: bool | None = None


class IntakeFieldOrderIn(BaseModel):
    """PUT /admin/intake-fields/order: every field key in the new order."""

    keys: list[Code] = Field(max_length=200)


# --------------------------------------------------------------------------- roles and users (1.6)


class RoleAdminOut(BaseModel):
    code: str
    label: str
    short_label: str
    phrase_label: str
    description: str = ""
    active: bool
    is_builtin: bool
    has_transition_slot: bool
    transition_column: str | None = None
    can_approve: bool
    sort_order: int
    color: str | None = None
    user_count: int = 0
    lock_reason: str | None = None


class RoleCreateIn(BaseModel):
    """POST /admin/roles. ``code`` is immutable; "Orion", "agent", "bot", "ai" are reserved."""

    code: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{1,29}$")]
    label: Text80
    short_label: Annotated[str, StringConstraints(max_length=40)] = ""
    phrase_label: Annotated[str, StringConstraints(max_length=40)] = ""
    description: LongText = ""
    has_transition_slot: bool = False
    can_approve: bool = False
    color: Text80 | None = None


class RoleUpdateIn(BaseModel):
    label: Text80 | None = None
    short_label: Annotated[str, StringConstraints(max_length=40)] | None = None
    phrase_label: Annotated[str, StringConstraints(max_length=40)] | None = None
    description: LongText | None = None
    active: bool | None = None
    has_transition_slot: bool | None = None
    can_approve: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    color: Text80 | None = None


class UserAdminOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    role_label: str = ""
    focal_label: str | None = None
    title: str | None = None
    active: bool = True
    assigned_transitions: int = 0  # active transitions where the person holds a slot


class UserCreateIn(BaseModel):
    """POST /admin/users: the id is generated (U17, U18, ...); the role must be an active role."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    role: Code
    focal_label: Text80 | None = None
    title: Annotated[str, StringConstraints(max_length=120)] | None = None


class UserUpdateIn(BaseModel):
    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
        | None
    ) = None
    email: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
        | None
    ) = None
    role: Code | None = None
    focal_label: Text80 | None = None
    title: Annotated[str, StringConstraints(max_length=120)] | None = None


class UserDeactivateIn(BaseModel):
    """``reassign_to``: a user of the same role who takes over the deactivated person's slots on
    active transitions (one audited action). Without it the slots stay (and show as inactive)."""

    reassign_to: str | None = None


class UserDeactivateOut(BaseModel):
    user: UserAdminOut
    assigned_transitions: int  # slots the person held on active transitions
    reassigned: int  # slots moved to ``reassign_to``
    warnings: list[str] = []


# --------------------------------------------------------------------------- permissions (1.6)


class PermissionRowOut(BaseModel):
    perm: str
    label: str
    description: str = ""
    area: str = ""
    scope: Scope  # transition-scoped permissions also need the person to be assigned (access.py)
    roles: list[str]  # roles that hold it
    denial_reason: str  # the current 403 / tooltip text
    default_denial_reason: str  # generated from the role labels (what a reset would write)
    is_custom: bool = False  # the text was edited by an Admin
    locked_roles: list[str] = []  # roles whose cell cannot be changed
    lock_reasons: dict[str, str] = {}  # role code -> why it is locked (tooltip)


class PermissionMatrixOut(BaseModel):
    """GET / PUT /admin/permissions. Columns = ``roles`` (active only), rows = ``permissions``."""

    roles: list[RoleAdminOut]
    permissions: list[PermissionRowOut]
    notices: list[str] = []


class PermissionTextIn(BaseModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    description: LongText | None = None
    denial_reason: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None
    ) = None


class PermissionsPutIn(BaseModel):
    """PUT /admin/permissions: the full matrix ``{perm: [role codes]}`` (every perm present) and
    optional text edits ``{perm: {...}}``. Guardrails: ADMIN keeps ``admin`` and one active user
    holds it; ``view`` includes every active role; no Orion / agent role."""

    matrix: dict[str, list[Code]]
    texts: dict[str, PermissionTextIn] = Field(default_factory=dict)


# --------------------------------------------------------------------------- tiering (1.7)


class TierDefIn(BaseModel):
    tier: int = Field(ge=1, le=9)
    name: Text200
    definition: LongText = ""
    examples: LongText = ""
    builder_persona: Text200 = ""


class TierQuestionIn(BaseModel):
    """``id`` empty = a new question (TQ6, TQ7 ... generated)."""

    id: Annotated[str, StringConstraints(pattern=r"^(TQ\d{1,3})?$")] = ""
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    hint: Text200 = ""
    active: bool = True


class TierQuestionOut(TierQuestionIn):
    id: str
    sort_order: int = 0


class TierConditionIn(BaseModel):
    """One condition of a rule. ``source`` question: ``key`` = a question id, op yes / no.
    ``source`` intake / custom: ``key`` = field key (an audience-style option list or a custom
    field), op equals / not_equals / in (``value`` = text, or a list for ``in``)."""

    source: Literal["question", "intake", "custom"]
    key: Code
    op: Literal["yes", "no", "equals", "not_equals", "in"]
    value: str | list[str] | None = None
    rationale: Text200 = ""


class TierRuleIn(BaseModel):
    id: Annotated[str, StringConstraints(max_length=20)] = ""  # empty = new (RULE-n generated)
    label: Text200 = ""
    result_tier: int = Field(ge=1, le=9)
    match: Literal["any", "all"] = "any"
    conditions: list[TierConditionIn] = Field(default_factory=list, max_length=20)
    active: bool = True


class TierRuleOut(TierRuleIn):
    id: str
    sort_order: int = 0


class TierSourceOut(BaseModel):
    """What a rule condition can look at: an intake field with its option values."""

    key: str
    label: str
    source: Literal["intake", "custom"]
    values: list[str] = []


class TieringConfigOut(BaseModel):
    """GET / PUT /admin/tiering."""

    tiers: list[TierDefIn]
    dimensions: list[str]
    default_tier: int
    questions: list[TierQuestionOut]
    rules: list[TierRuleOut]  # evaluation order; the first match wins
    sources: list[TierSourceOut] = []
    notice: str = "Applies to new tier proposals; confirmed tiers stay as they are."


class TieringConfigIn(BaseModel):
    """PUT: the whole tiering configuration (list order = evaluation order). Guardrails: tier numbers
    unique and contiguous from 1, rules reference existing questions, ``default_tier`` is defined.
    """

    tiers: list[TierDefIn] = Field(min_length=1, max_length=9)
    dimensions: list[Annotated[str, StringConstraints(max_length=300)]] = Field(max_length=10)
    default_tier: int = Field(ge=1, le=9)
    questions: list[TierQuestionIn] = Field(max_length=30)
    rules: list[TierRuleIn] = Field(max_length=50)


class TierTestIn(BaseModel):
    """POST /admin/tiering/test: runs the pure ``propose_tier`` on a hypothetical project."""

    intake: dict[str, str | None] = Field(default_factory=dict)  # e.g. {"audience": "External"}
    answers: dict[str, bool] = Field(default_factory=dict)  # {"TQ1": true}
    config: TieringConfigIn | None = None  # test unsaved edits; omitted = the saved configuration


class TierTestOut(BaseModel):
    tier: int
    rationale: list[str]
    matched_rule_id: str | None = None  # None = default tier


# --------------------------------------------------------------------------- eval metrics (1.7)


class EvalMetricCreateIn(BaseModel):
    """POST /admin/eval-metrics: a new metric EV-nn with a target per tier (``cfg.tiers``)."""

    metric: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    evaluation: Literal["auto", "manual"] = "manual"
    unit: Annotated[str, StringConstraints(max_length=10)] | None = None
    operator: Literal[">=", "<=", "<", ">", "==", "abs<="] | None = None
    value: float | None = None
    targets_by_tier: dict[str, Annotated[str, StringConstraints(max_length=200)]] = Field(
        default_factory=dict
    )


class EvalMetricUpdateIn(BaseModel):
    metric: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
        | None
    ) = None
    evaluation: Literal["auto", "manual"] | None = None
    unit: Annotated[str, StringConstraints(max_length=10)] | None = None
    active: bool | None = None


class EvalMetricAdminOut(BaseModel):
    id: str
    metric: str
    evaluation: str
    unit: str | None = None
    active: bool = True
    targets_by_tier: dict[str, str] = {}
    notice: str = NOTICE_NEW_ONLY


# --------------------------------------------------------------------------- settings documents (1.8)


class RagThresholdsDoc(BaseModel):
    red_critical_gaps: int = Field(ge=1, le=100)
    red_lens_below: int = Field(ge=0, le=100)
    red_near_days: int = Field(ge=0, le=365)
    amber_critical_gaps: int = Field(ge=1, le=100)
    amber_lens_below: int = Field(ge=0, le=100)


class InsightsThresholdsDoc(BaseModel):
    low_readiness_below: int = Field(ge=0, le=100)
    within_days: int = Field(ge=0, le=365)


class DashboardThresholdsDoc(BaseModel):
    my_work_limit: int = Field(ge=1, le=1000)
    recent_activity_limit: int = Field(ge=1, le=100)


class ThresholdsDoc(BaseModel):
    """``cfg.thresholds``. Guardrail: amber is not stricter than red."""

    rag: RagThresholdsDoc
    insights: InsightsThresholdsDoc
    calendar_horizon_days: int = Field(ge=0, le=365)
    leadership_decision_window_days: int = Field(ge=0, le=365)
    dashboard: DashboardThresholdsDoc
    narrative_top: int = Field(ge=1, le=20)
    default_tier: int = Field(ge=1, le=9)
    default_pricing_basis: Text80
    default_horizon_years: int = Field(ge=1, le=30)
    default_growth_pct: float = Field(ge=-100, le=1000)


class ThresholdsOut(BaseModel):
    thresholds: ThresholdsDoc
    rag_rule: dict[str, str]  # display text GENERATED from the numbers
    notice: str = NOTICE_LIVE


class ThresholdsIn(BaseModel):
    thresholds: ThresholdsDoc


class LabelsDoc(BaseModel):
    """Display overrides of workflow vocabulary: ``{key: label}`` (e.g. ``"rag.Grey": "Not started"``).
    Keys are the ones returned by GET (unknown keys are refused)."""

    labels: dict[
        str, Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    ]


class LabelsOut(LabelsDoc):
    defaults: dict[str, str] = {}
    notice: str = "Changes the wording only; behaviour does not change."


class GateTextIn(BaseModel):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    short: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    description: LongText = ""


class GateTextOut(GateTextIn):
    code: str
    order: int
    type: str  # stage_review | decision | closure (structural, code)


class GatesDoc(BaseModel):
    """Gate texts keyed by gate code (codes, order and type stay in code), outcome label overrides
    ``{gate_type: {outcome: label}}`` and the decision-gate -> approval-chain map."""

    gates: dict[str, GateTextIn]
    outcome_labels: dict[str, dict[str, str]] = Field(default_factory=dict)
    chain: dict[str, Annotated[str, StringConstraints(max_length=30)]] = Field(default_factory=dict)
    mock_role: str | None = None  # the mocked approval role (CISO_BISO)
    mock_approver_role: str | None = None  # the real role that acts for it (IRM)


class GatesOut(BaseModel):
    gates: list[GateTextOut]
    outcome_labels: dict[str, dict[str, str]]
    outcomes: dict[str, list[str]]  # gate type -> outcome values (structural)
    chain: dict[str, str]
    mock_role: str
    mock_approver_role: str
    notice: str = "Codes, order and gate types are fixed; the wording is yours."


class LensCfgIn(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    color_hint: Text80
    owner_roles: list[Code] = Field(max_length=10)
    signoff_role: Code


class LensesDoc(BaseModel):
    """The three lenses (Business, Technical, Compliance - structural) keyed by code."""

    lenses: dict[str, LensCfgIn]


class LensesOut(LensesDoc):
    notice: str = "The three lenses are fixed; their question, colour and owners are yours."


# --------------------------------------------------------------------------- message templates (1.8)


class PlaceholderOut(BaseModel):
    name: str
    description: str = ""
    html: bool = False  # inserted as given (an already-escaped fragment); others are escaped


class MessageTemplateAdminOut(BaseModel):
    key: str
    name: str
    subject: str
    body: str
    enabled: bool = True
    placeholders: list[PlaceholderOut]
    is_default: bool = True  # no row saved: this is the code default
    code_source: str = ""  # which code path produced this text before CR-01
    default_subject: str
    default_body: str
    notice: str = (
        "Orion drafts, you decide: only the wording changes, never who receives it or when."
    )


class MessageTemplateIn(BaseModel):
    key: Annotated[str, StringConstraints(max_length=60)]
    subject: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    body: Annotated[str, StringConstraints(min_length=1, max_length=8000)]
    enabled: bool = True


class MessageTemplatesPutIn(BaseModel):
    templates: list[MessageTemplateIn] = Field(max_length=50)


class TemplatePreviewIn(BaseModel):
    """POST /admin/message-templates/{key}/preview: sample context render. ``subject`` / ``body``
    preview unsaved edits; omitted = the saved template. ``context`` overrides sample values."""

    subject: str | None = None
    body: str | None = None
    context: dict[str, str] = Field(default_factory=dict)


class TemplatePreviewOut(BaseModel):
    subject: str
    body_html: str
    unknown_placeholders: list[str] = []


# --------------------------------------------------------------------------- export / import, usage


class ConfigExportOut(BaseModel):
    """GET /admin/config-export (stretch): every configuration section as JSON."""

    schema_version: int
    sections: dict[str, Any]


class ConfigImportIn(BaseModel):
    schema_version: int
    sections: dict[str, Any]


class ConfigDiffOut(BaseModel):
    """POST /admin/config-import?dry_run=true: what the import would add, change and remove."""

    dry_run: bool
    applied: bool
    added: dict[str, list[str]] = {}
    changed: dict[str, list[str]] = {}
    removed: dict[str, list[str]] = {}
    reasons: list[str] = []


class UsageTransitionOut(BaseModel):
    id: str
    name: str


class UsageOut(BaseModel):
    """GET /admin/usage?kind=&key=: where a value is used (first 10 transitions)."""

    kind: str
    key: str
    count: int
    transitions: list[UsageTransitionOut] = []
