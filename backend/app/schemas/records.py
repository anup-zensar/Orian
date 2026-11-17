"""Workspace records: evidence, actions, conditions, risks, hypercare defects (spec §6, §8.7 c/d/f/g)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import PersonRef

EvidenceType = Literal["Document", "Link", "Email sign-off", "Recording", "Generated"]
EvidenceStatus = Literal["Submitted", "Accepted", "Rejected"]
ActionStatus = Literal["Open", "In progress", "Done", "Cancelled"]
Priority3 = Literal["High", "Medium", "Low"]
DefectPriority = Literal["P1", "P2", "P3", "P4"]
DefectStatus = Literal["Open", "Resolved"]


# --- evidence -----------------------------------------------------------------------------------
class EvidenceFilters(BaseModel):
    item: str | None = Field(default=None, description="Playbook item id, e.g. S45-014")
    type: EvidenceType | None = None
    status: EvidenceStatus | None = None


class EvidenceOut(BaseModel):
    id: str  # EVD-001
    transition_id: str
    item_id: str | None  # playbook id
    transition_item_id: int | None
    item_title: str | None
    title: str
    type: str
    url: str  # link, or fake SharePoint URL for uploaded files
    has_file: bool  # a file is stored -> /evidence/{id}/download works
    text: str | None  # email sign-off text
    submitted_by: PersonRef | None
    status: EvidenceStatus
    reviewed_by: PersonRef | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    can_review: bool  # current user may Accept/Reject (OR focal for B/T items, IRM for C)
    review_denied_reason: str | None


class EvidenceReviewIn(BaseModel):
    decision: Literal["Accept", "Reject"]
    note: str = ""


# --- actions ------------------------------------------------------------------------------------
class ActionOut(BaseModel):
    id: str  # ACT-001
    title: str
    item_ids: list[str]  # playbook ids
    owner: PersonRef | None
    due_date: date | None
    days_until_due: int | None  # negative when overdue; None without due date (clock.today())
    overdue: bool  # due_date < today and status in Open / In progress
    status: ActionStatus
    priority: Priority3
    origin: str  # "Human" | "Orion proposal accepted by <name>"
    created_by: PersonRef | None
    created_at: datetime


class ActionCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    item_ids: list[str] = []
    owner_user_id: str
    due_date: date
    priority: Priority3 = "Medium"


class ActionPatchIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    owner_user_id: str | None = None
    due_date: date | None = None
    status: ActionStatus | None = None
    priority: Priority3 | None = None


# --- conditions ---------------------------------------------------------------------------------
class ConditionOut(BaseModel):
    id: str  # CON-001
    item_id: str | None  # playbook id
    transition_item_id: int | None
    item_title: str | None
    set_at_gate: str
    set_at_gate_short: str
    due_gate: str
    due_gate_short: str
    owner: PersonRef | None
    text: str
    status: Literal["Open", "Closed"]
    covers_now: bool  # Open and due_gate after the transition's current gate (BR-020, A-33)
    closed_by: PersonRef | None
    closed_at: datetime | None
    close_note: str | None


class ConditionCreateIn(BaseModel):
    item_id: str | None = Field(default=None, description="Playbook item id the condition covers")
    owner_user_id: str
    due_gate: str
    text: str = Field(min_length=1)


class ConditionPatchIn(BaseModel):
    """Either close (status "Closed" + close_note) or edit owner / due_gate / text of an Open condition."""

    status: Literal["Closed"] | None = None
    close_note: str | None = None
    owner_user_id: str | None = None
    due_gate: str | None = None
    text: str | None = Field(default=None, min_length=1)


# --- risks --------------------------------------------------------------------------------------
class RiskOut(BaseModel):
    id: str  # CR-01
    title: str
    rating: Priority3
    decision: str
    item_ids: list[str]


class RiskCreateIn(BaseModel):
    title: str = Field(min_length=1)
    rating: Priority3
    decision: str = ""
    item_ids: list[str] = []


# --- hypercare defects --------------------------------------------------------------------------
class DefectOut(BaseModel):
    id: str  # DEF-001
    title: str
    priority: DefectPriority
    status: DefectStatus
    owner: PersonRef | None


class DefectCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    priority: DefectPriority
    owner_user_id: str | None = None


class DefectPatchIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    priority: DefectPriority | None = None
    status: DefectStatus | None = None
    owner_user_id: str | None = None


class ConfirmNoDefectsIn(BaseModel):
    confirmed: bool


class HypercareOut(BaseModel):
    defects: list[DefectOut]
    no_defects_confirmed: bool
    tracker_in_place: (
        bool  # at least one defect exists OR no_defects_confirmed (feeds UD-002 / AtO rules)
    )
    open_p1_p2: int  # Open defects with priority P1 or P2
