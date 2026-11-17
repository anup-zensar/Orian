"""Approval chain DTOs (spec §6 ApprovalRequest, §8.11 FR-070, BR-041)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import PersonRef

ApprovalType = Literal["OCET", "AtD", "AtO", "SUPPORT_MODEL", "EXCEPTION", "RISK_ACCEPTANCE"]
ApprovalStatus = Literal["Pending", "Approved", "Rejected", "Cancelled"]
StepStatus = Literal["Waiting", "Pending", "Approved", "Rejected", "Cancelled"]


class ApprovalStepOut(BaseModel):
    step: int  # 1-based, sequential
    role: str  # PLANNER | OLM | IRM | ARCHITECT | CISO_BISO
    label: str  # e.g. "IRM review"
    approver: PersonRef | None  # None for CISO_BISO (mocked, no real person)
    status: StepStatus
    activated_at: datetime | None  # when the step became Pending
    decided_at: datetime | None
    decided_by: PersonRef | None
    comment: str | None
    # whole days the step has been Pending (clock.now - activated_at) while Pending, else 0
    waiting_days: int = 0


class ApprovalRequestOut(BaseModel):
    id: str  # APR-0001
    type: ApprovalType
    type_label: str  # "OCET approval" | "Authority to Deploy" | "Authority to Operate" | ...
    transition_id: str
    transition_name: str
    gate: str | None  # SG4_ATD ... for AtD/AtO
    gate_short: str | None  # "ATD" | "ATO" label for chips
    subject_id: str | None
    subject_label: str
    status: ApprovalStatus
    created_by: PersonRef | None
    created_source: str  # Human | Workflow rule | Orion agent | System
    created_at: datetime
    age_days: int  # whole days since created_at
    steps: list[ApprovalStepOut]
    current_step: int | None  # step number that is Pending, None once finished
    can_act: bool  # requesting user may approve/reject the current step right now
    act_denied_reason: str | None  # tooltip when can_act is False and status is Pending
    is_mock_step: bool  # current step is CISO_BISO: approvable by IRM in demo mode, labelled mock
    link: str  # deep link to the subject, e.g. /transitions/TR-0001?tab=ocet


class ApprovalDecisionIn(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class ApprovalRejectIn(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)
