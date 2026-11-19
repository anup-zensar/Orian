"""Admin configuration + demo-control DTOs (spec 6, 8.16, 9 Admin). M9 contract."""

from __future__ import annotations

from datetime import date as Date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

ADMIN_NOTICE = "Changes affect new transitions; existing transitions keep their items."

Lens = Literal["Business", "Technical", "Compliance"]
ChecklistSource = str  # a checklist code; checked against the checklist registry (cfg)
Operator = Literal[">=", "<=", "<", ">", "==", "abs<="]
ChainType = Literal["OCET", "AtD", "AtO", "SUPPORT_MODEL", "EXCEPTION"]


class PlaybookItemAdminOut(ORMModel):
    """Every PlaybookItem field plus the "lens suggested - confirm" badge flag (spec 8.16)."""

    id: str
    source: str
    source_label: str = ""
    portfolio: str | None = None
    title: str
    description: str = ""
    detail: str = ""
    gate: str
    lens: str
    secondary_lens: str = ""
    lens_is_suggested: bool = False
    lens_suggested: bool = False  # badge flag, == lens_is_suggested
    category: str = ""
    kind: str = ""
    applicable_tiers: list[int] = Field(default=[], max_length=8)
    tier_label: str = ""
    tier_unspecified: bool = False
    mandatory: bool = True
    mandatory_rule: str | None = None
    applies_to_project_types: list[str] = []
    owner_role_hint: str = ""
    active: bool = True
    linked_module: str | None = None  # OCET | SUPPORT_MODEL | None (A-10)
    notice: str = ADMIN_NOTICE


class PlaybookItemUpdateIn(BaseModel):
    """PUT body; full replacement of the editable fields."""

    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=4000)
    gate: str = Field(max_length=20)  # gate code, e.g. SG4_ATD (422 if unknown)
    lens: Lens
    applicable_tiers: list[int] = []  # each 1..4 (422 otherwise)
    mandatory: bool = True
    active: bool = True


class FlavourRuleOut(ORMModel):
    """A project type. The first four fields are the original contract; the rest is CR-01."""

    project_type: str
    checklists: list[str]
    requires_tiering: bool = False
    note: str | None = None
    label: str = ""
    description: str = ""
    active: bool = True
    has_ai_profile: bool = False
    has_eval_metrics: bool = False
    required_intake_fields: list[str] = []
    synonyms: list[str] = []


class FlavourRuleIn(BaseModel):
    project_type: str = Field(max_length=100)
    checklists: list[ChecklistSource] = Field(max_length=8)
    requires_tiering: bool = False
    note: str | None = Field(default=None, max_length=1000)


class FlavourRulesOut(BaseModel):
    rules: list[FlavourRuleOut]
    notice: str = ADMIN_NOTICE


class FlavourRulesIn(BaseModel):
    """PUT body: one entry per existing project_type (unknown types -> 422; none created/deleted)."""

    rules: list[FlavourRuleIn] = Field(max_length=50)


class GoldenSetItemOut(BaseModel):
    id: str  # "<CODE>-NN", e.g. GCC-01
    title: str
    gate: str
    owner_role_hint: str = ""
    lens: str
    mandatory: bool = True
    active: bool = True


class GoldenSetItemIn(BaseModel):
    """``id`` null/empty = new item (server assigns the next "<CODE>-NN"); existing id = edit."""

    id: str | None = Field(default=None, max_length=20)
    title: str = Field(min_length=1, max_length=500)
    gate: str = Field(max_length=20)
    owner_role_hint: str = Field(default="", max_length=100)
    lens: Lens
    mandatory: bool = True


class GoldenSetOut(BaseModel):
    portfolio: str
    focus_areas: list[str]
    items: list[GoldenSetItemOut]  # includes deactivated rows (active=false)
    notice: str = ADMIN_NOTICE


class GoldenSetIn(BaseModel):
    focus_areas: list[Annotated[str, Field(max_length=200)]] | None = Field(
        default=None, max_length=50
    )  # null = leave unchanged
    items: list[GoldenSetItemIn] = Field(max_length=300)


class EvalTierTargetOut(BaseModel):
    tier: int  # 1..4
    target_text: str
    operator: str | None = None
    value: float | None = None
    unit: str | None = None


class EvalMetricOut(BaseModel):
    metric_id: str  # EV-01
    metric: str
    evaluation: str  # auto | manual
    tiers: list[EvalTierTargetOut]


class EvalTargetsOut(BaseModel):
    confirmed: bool
    metrics: list[EvalMetricOut]
    notice: str = ADMIN_NOTICE


class EvalTierTargetIn(BaseModel):
    tier: int = Field(ge=1, le=4)
    target_text: str = Field(min_length=1, max_length=200)
    operator: Operator | None = None
    value: float | None = None
    unit: str | None = Field(default=None, max_length=10)


class EvalMetricIn(BaseModel):
    metric_id: str = Field(max_length=20)
    tiers: list[EvalTierTargetIn] = Field(max_length=8)


class EvalTargetsIn(BaseModel):
    confirmed: bool
    metrics: list[EvalMetricIn] = Field(max_length=100)


class ChainStep(BaseModel):
    step: int = Field(ge=1)
    role: str = Field(max_length=30)  # a role code (can_approve) or CISO_BISO (422 otherwise)
    label: str = Field(max_length=100)
    is_mock: bool = False  # a mocked step: IRM acts for it in demo mode


class ApprovalChainOut(BaseModel):
    type: ChainType
    steps: list[ChainStep]
    label: str | None = Field(
        default=None, max_length=80
    )  # display name, e.g. "Agreement to Deploy"


class ApprovalChainsOut(BaseModel):
    chains: list[ApprovalChainOut]
    roles: list[str] = []  # allowed role values for the step pickers
    notice: str = ADMIN_NOTICE


class ApprovalChainsIn(BaseModel):
    chains: list[ApprovalChainOut] = Field(max_length=10)


class ReminderRuleOut(ORMModel):
    id: str  # R1..R7
    name: str
    description: str = ""
    enabled: bool = True
    autonomous_eligible: bool = False
    params: dict[str, Any] = {}  # e.g. {"days_before_decision": 14}


class ReminderRuleIn(BaseModel):
    id: str = Field(max_length=20)
    enabled: bool
    params: dict[str, Any] = Field(
        default={}, max_length=20
    )  # numeric thresholds must be positive ints (422 otherwise); R6 also item_ids / category
    autonomous_eligible: bool | None = None  # None = unchanged; it can only be switched OFF


class ReminderRulesIn(BaseModel):
    rules: list[ReminderRuleIn] = Field(max_length=50)


class DemoResetOut(BaseModel):
    seconds: float
    transitions: int
    items: int


class FastForwardIn(BaseModel):
    transition_id: str = "TR-0001"


class FastForwardOut(BaseModel):
    transition_id: str
    items_completed: int
    skipped_linked: int  # OCET / SUPPORT_MODEL linked items left open
    skipped_exception: int  # items under an exception left open
    evals_passing: int  # eval metrics re-imported as passing
    readiness: str | None = None  # verdict text if available
    r4_drafts: int = 0  # "Ready for AtD" drafts created by rule R4 (open Orion drafts to send)


class TodayIn(BaseModel):
    date: Date | None = None  # null clears the override (back to SEED_DATE / real date)


class TodayOut(BaseModel):
    today: Date
    override: Date | None = None
    seed_date: Date | None = None


class ApprovalCancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ApprovalCancelOut(BaseModel):
    request_id: str
    status: str
