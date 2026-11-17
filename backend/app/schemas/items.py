"""Checklist items on a transition (spec §6 TransitionItem, §7.3, §7.5 BR-030, §8.7 a/b, §9 Scope & items).

Vocabulary comes from ``app.rules.constants``: lens statuses (``STATUSES_BY_LENS``), severities
(Critical | Major | Minor), design effectiveness (-, Yes, No, N/A), applicability
(Applies | Not applicable | To confirm).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import PersonRef

Lens = Literal["Business", "Technical", "Compliance"]
ItemSource = Literal["FRAMEWORK", "AI_PLAYBOOK", "PORTFOLIO", "COMMON"]
Severity = Literal["Critical", "Major", "Minor"]
DesignEffectiveness = Literal["–", "Yes", "No", "N/A"]
Applicability = Literal["Applies", "Not applicable", "To confirm"]
ApplicabilityFilter = Literal["applies", "excluded", "to_confirm", "all"]


class ItemFilters(BaseModel):
    """Query filters for ``GET /transitions/{id}/items`` (all optional, AND-combined)."""

    gate: str | None = Field(
        default=None,
        description="Gate code. Default: the transition's current gate. Returns items due AT OR BEFORE "
        "this gate (GATE_ORDER) unless all_gates is true",
    )
    all_gates: bool = Field(default=False, description="Ignore the gate cut-off (every gate)")
    lens: Lens | None = None
    source: ItemSource | None = None
    status: str | None = Field(default=None, description="Exact item status, e.g. 'Gap'")
    owner: str | None = Field(default=None, description="Owner user id")
    mine: bool = Field(default=False, description="Only items owned by the current user")
    applicability: ApplicabilityFilter = Field(
        default="applies",
        description="applies = Applies; excluded = Not applicable (tier / project type / portfolio / "
        "manual N/A); to_confirm = To confirm; all = everything",
    )
    q: str | None = Field(
        default=None,
        description="Case-insensitive search in playbook id, title, description and owner name",
    )


class ItemOut(BaseModel):
    """One checklist row (spec §8.7 b). ``id`` is the TransitionItem integer key used by PATCH /items/{id};
    ``item_id`` is the playbook id (S45-014) shown to humans and used by evidence/actions/risks."""

    id: int
    item_id: str
    title: str
    description: str
    detail: str
    source: ItemSource
    source_label: str
    source_sheet: str
    source_cell: str
    category: str
    kind: str  # Check | Question | KPI | Evidence | Support model | Deliverable
    gate: str  # due gate code
    gate_short: str
    lens: Lens
    lens_is_suggested: bool  # AI-playbook lens mapping is a suggestion (badge "suggested")
    tier_label: str
    tier_to_confirm: bool  # playbook tier_unspecified (AI items): "tier to be confirmed"
    applicability: Applicability
    excluded_by: str | None  # tier | project_type | portfolio
    na_reason: str | None
    status: str
    allowed_statuses: list[str]  # STATUSES_BY_LENS[lens]
    gap_severity: Severity | None
    design_effectiveness: DesignEffectiveness | None  # Compliance items only
    note: str
    owner: PersonRef | None
    linked_module: str | None  # OCET | SUPPORT_MODEL
    evidence_count: int
    open_condition_id: str | None  # an Open condition on this item (CON-001)
    exception_ref: str | None  # latest exception on this item (EX-01)
    exception_status: str | None  # Draft | Pending CISO/BISO | Approved | Rejected
    covered: bool  # open item covered by an open condition due after the current gate (BR-020)
    last_updated_by: PersonRef | None
    last_updated_source: str  # Human | Workflow rule | System
    updated_at: datetime
    can_edit: bool  # current user may change status for this item's lens
    edit_denied_reason: str | None  # DENIAL_REASONS text when can_edit is false


class GateLensSummaryOut(BaseModel):
    """Gate summary bar row for the selected gate (spec §8.7 b), one per lens, live (BR-020)."""

    lens: Lens
    scope: int  # applicable items due <= gate, excluding N/A
    done: int
    in_progress: int
    not_started: int
    open_gaps: int
    critical_gaps: int
    readiness_pct: int


class ItemListOut(BaseModel):
    gate: str  # effective gate code used
    items: list[ItemOut]  # sorted by gate order, lens (Business, Technical, Compliance), sort_order
    summary: list[GateLensSummaryOut]  # always 3 rows, Business/Technical/Compliance
    excluded_count: int  # items with applicability "Not applicable" on this transition
    excluded_by_tier_count: int  # of those, excluded_by == "tier"


class ItemConditionIn(BaseModel):
    owner_user_id: str
    due_gate: str
    text: str


class ItemPatchIn(BaseModel):
    """Partial update; only fields present in the body are applied (``model_fields_set``)."""

    status: str | None = None
    gap_severity: Severity | None = None
    note: str | None = None
    owner_user_id: str | None = None
    design_effectiveness: DesignEffectiveness | None = None
    applicability: Applicability | None = None
    na_reason: str | None = None
    condition: ItemConditionIn | None = Field(
        default=None, description="Required when status is 'Compliant with conditions'"
    )


class BulkNaIn(BaseModel):
    reason: str


class BulkItemsIn(BaseModel):
    item_ids: list[int] = Field(min_length=1)
    owner_user_id: str | None = None
    mark_na: BulkNaIn | None = None


class BulkSkippedOut(BaseModel):
    id: int
    reason: str


class BulkResultOut(BaseModel):
    updated: list[int]
    skipped: list[BulkSkippedOut]
