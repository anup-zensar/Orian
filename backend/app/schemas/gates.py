"""Gates & readiness DTOs (spec 4, 7.5, 7.6, 8.7e, 8.9, 9 Gates & approvals). M5 contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import LensValues, PersonRef

Verdict = Literal["Ready", "Ready with conditions", "Not ready"]
GateState = Literal["done", "current", "upcoming"]
RecommendedKind = Literal[
    "draft_chaser",
    "create_action",
    "request_inputs",
    "open_ocet",
    "create_support_model",
    "request_exception",
    "request_approval",
]


class GateItemRef(BaseModel):
    """An item shown in the readiness check. ``item_id`` is the PLAYBOOK item id (e.g. S45-014)."""

    item_id: str
    title: str
    lens: str = ""
    status: str
    gap_severity: str | None = None
    owner: PersonRef | None = None
    reason: str  # why it blocks, e.g. "Non-compliant (Critical) - exception EX-01 pending"


class BlockingGroup(BaseModel):
    lens: str  # Business | Technical | Compliance
    items: list[GateItemRef]  # failed eval metrics appear in Technical (item_id = metric id)


class OpenConditionOut(BaseModel):
    id: str  # CON-001
    item_id: str | None
    text: str
    due_gate: str
    owner: PersonRef | None = None


class CarriedItemOut(BaseModel):
    """Open item conditioned at an earlier gate: "Carried from SG3: S3-019 ... owner Asha, due AtD"."""

    item_id: str
    title: str
    lens: str = ""
    status: str
    condition_id: str
    set_at_gate: str
    due_gate: str
    owner: PersonRef | None = None
    text: str = ""


class PendingExceptionOut(BaseModel):
    ref: str  # EX-01
    item_id: str | None
    status: str


class FailedEvalOut(BaseModel):
    metric_id: str
    metric: str
    result: str
    target_text: str


class ApprovalStepOut(BaseModel):
    step: int
    role: str
    label: str
    approver: PersonRef | None = None
    status: str  # Waiting | Pending | Approved | Rejected | Cancelled


class GateApprovalOut(BaseModel):
    request_id: str  # APR-0001
    status: str  # Pending | Approved | Rejected | Cancelled
    steps: list[ApprovalStepOut]


class DecisionOption(BaseModel):
    """One outcome button of the decision / review dialog; ``reasons`` explain a disabled button
    (tooltip, AC-08). ``reasons`` is empty when enabled."""

    outcome: str
    enabled: bool
    reasons: list[str] = []


class RecommendedAction(BaseModel):
    """Orion agent proposal (BR-050: the human clicks, nothing executes automatically)."""

    key: str
    label: str
    kind: RecommendedKind
    item_ids: list[str] = []
    href: str | None = None  # route for open_ocet / create_support_model


class ReadinessCheckOut(BaseModel):
    gate: str
    gate_short: str
    gate_type: str  # stage_review | decision | closure
    verdict: Verdict
    verdict_label: str  # "Not ready for AtD" | "Ready for AtD" | "Ready with conditions for AtD"
    lenses: LensValues  # readiness % per lens at that gate
    blocking: list[BlockingGroup]  # only lenses with items; order Business, Technical, Compliance
    critical_gaps: list[GateItemRef]
    open_conditions: list[OpenConditionOut]  # open, due <= gate
    carried_items: list[CarriedItemOut]
    pending_exceptions: list[PendingExceptionOut]
    failed_evals: list[FailedEvalOut]
    unevaluated_evals: int = 0  # warning only, never blocks
    ocet_status: str | None = None  # None = no OCET; else e.g. "Draft v2", "Approved v2"
    support_model_status: str | None = None  # None = not created; Draft | In review | Agreed ...
    approval: GateApprovalOut | None = None
    can_request_approval: bool
    request_denied_reason: str | None = None
    decision_options: list[DecisionOption]
    narrative: str  # Orion agent text (mock AI, 3-5 sentences)
    narrative_by: str = "Orion agent"
    recommended_actions: list[RecommendedAction]
    warnings: list[str] = []
    generated_at: datetime


class GateReviewRecord(BaseModel):
    id: int
    gate: str = ""
    gate_type: str = ""
    outcome: str
    decided_by: PersonRef | None
    decided_at: datetime
    note: str = ""
    conditions_created: list[str] = []  # condition ids


class GateOverview(BaseModel):
    code: str
    short: str
    label: str
    type: str  # stage_review | decision | closure
    state: GateState
    reviews: list[GateReviewRecord]  # chronological; a gate can have Hold then Proceed
    carried_items: int  # carried items shown on this gate's page
    approval: GateApprovalOut | None = None  # latest AtD / AtO chain for decision gates


class GatesOverviewOut(BaseModel):
    current_gate: str
    gates: list[GateOverview]  # all 7 gates in order


class ConditionIn(BaseModel):
    """Condition requested with a Proceed / Approve-with-conditions outcome (BR-040)."""

    item_id: str  # playbook item id
    owner_user_id: str
    due_gate: str  # strictly later than the gate being decided
    text: str = Field(min_length=1)


class GateReviewIn(BaseModel):
    outcome: str  # Proceed | Proceed with conditions | Hold
    note: str = ""  # required for Hold
    conditions: list[ConditionIn] = []


class GateDecisionIn(BaseModel):
    decision: str  # Approve | Approve with conditions | Return | Close
    note: str = ""  # required for Return
    conditions: list[ConditionIn] = []


class GateReviewOut(BaseModel):
    review: GateReviewRecord
    new_current_gate: str  # unchanged after Hold / Return; next gate after Proceed / Approve
    conditions_created: list[str]  # condition ids
    transition_closed: bool = False  # True after Close at CLOSURE


class GateApprovalRequestIn(BaseModel):
    note: str | None = None
    draft_id: int | None = None  # accepted Orion draft this request is sent from (assistive mode)


class GateApprovalRequestOut(BaseModel):
    request_id: str
    status: str
    steps: list[ApprovalStepOut]
