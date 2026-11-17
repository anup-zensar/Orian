"""OCET DTOs (spec 6 OcetEstimate/Version/Line, 7.9, 8.10 FR-060, 9). M6."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import PersonRef

OcetStatus = Literal[
    "Draft", "Inputs pending", "Submitted", "Planner approved", "Approved", "Rejected", "Superseded"
]
InputStatus = Literal["Provided", "Requested", "Missing"]
RowStatus = Literal["added", "removed", "changed", "same"]


class YearAmount(BaseModel):
    year: int
    amount: float  # full precision; UI formats ("146.4k" in charts, full numbers in the table)


class OcetEstimateOut(BaseModel):
    id: int
    currency: str
    start_year: int
    horizon_years: int
    current_version: int  # version number (not id)


class OcetVersionOut(BaseModel):
    id: int
    version: int
    status: OcetStatus
    note: str
    created_by: PersonRef | None
    created_at: datetime
    submitted_at: datetime | None
    approval_request_id: str | None  # APR-0001
    total: float  # horizon total (missing bases count 0)


class OcetCurrentVersionOut(OcetVersionOut):
    can_edit: bool  # Perm.EDIT_OCET and status Draft / Inputs pending
    edit_denied_reason: str | None  # tooltip when can_edit is False
    can_submit: bool  # can_edit, status Draft, every base amount present
    submit_denied_reasons: list[str]  # e.g. ["Monitoring tool: base amount missing"]
    inputs_pending: bool  # any line without base amount
    missing_line_ids: list[int]  # lines with no base amount (feeds "Request inputs")


class OcetLineOut(BaseModel):
    id: int
    line_key: str  # "L1", stable across versions
    category: str
    description: str
    vendor: str
    pricing_basis: str
    base_amount: float | None  # start-year amount; None = missing input
    growth_pct: float
    year_overrides: dict[int, float]  # year -> growth % into that year
    override_reason: str | None
    input_owner_role: str
    input_owner: PersonRef | None
    input_status: InputStatus
    input_requested_at: datetime | None
    requested_days: int = 0  # whole days since input_requested_at while Requested (R5 hint)
    yearly: list[YearAmount]  # computed, read-only
    total: float


class CategoryTotalOut(BaseModel):
    category: str
    amounts: list[YearAmount]
    total: float


class VarianceRowOut(BaseModel):
    key: str  # line_key (by_line) or category name (by_category)
    category: str
    description: str  # line description; "" for category rows
    previous_total: float
    current_total: float
    abs_change: float
    pct_change: float | None  # None when previous_total is 0
    status: RowStatus


class VarianceOut(BaseModel):
    previous_version: int | None  # None for v1 (everything "added")
    total_abs: float
    total_pct: float | None
    by_category: list[VarianceRowOut]
    by_line: list[VarianceRowOut]


class OcetApprovalStepOut(BaseModel):
    step: int
    role: str  # PLANNER | OLM
    label: str
    approver: PersonRef | None
    status: Literal["Waiting", "Pending", "Approved", "Rejected", "Cancelled"]


class OcetApprovalOut(BaseModel):
    request_id: str
    status: Literal["Pending", "Approved", "Rejected", "Cancelled"]
    steps: list[OcetApprovalStepOut]


class OcetOut(BaseModel):
    """Everything the OCET screen (spec 8.10) needs, for the CURRENT version."""

    transition_id: str
    estimate: OcetEstimateOut
    years: list[int]
    versions: list[OcetVersionOut]  # all versions, ascending
    version: OcetCurrentVersionOut
    lines: list[OcetLineOut]
    category_totals: list[CategoryTotalOut]
    grand_total_by_year: list[YearAmount]
    total: float
    total_label: str  # "1.92M" (rules.ocet.format_total_label)
    variance: VarianceOut
    approval: OcetApprovalOut | None
    explanation: str | None  # Orion agent text (AI badge), None for an empty version
    worked_example: str = "100k at +10% compounding -> 110k, 121k, 133.1k, 146.4k"
    info_note: str = "R&M costs are picked up by SOM per the ATO+12 principle"
    categories: list[str]  # reference ocet.categories
    pricing_bases: list[str]  # reference ocet.pricing_basis
    currencies: list[str]  # reference ocet.currencies
    default_growth_pct: dict[str, float] = {}  # reference ocet.default_growth_pct by category


class OcetLineIn(BaseModel):
    id: int | None = None  # None = new line
    line_key: str | None = Field(default=None, max_length=10)
    category: str
    description: str = Field(default="", max_length=2000)
    vendor: str = Field(default="", max_length=120)
    pricing_basis: str = "Fixed (contract)"
    base_amount: float | None = Field(default=None, ge=0, le=1e12)
    growth_pct: float = Field(default=0.0, ge=-100, le=1000)
    year_overrides: dict[int, float] = Field(default_factory=dict)
    override_reason: str | None = Field(default=None, max_length=2000)  # required with overrides
    input_owner_role: str = "PM"
    input_owner_user_id: str | None = None
    input_status: InputStatus = "Provided"


class OcetSaveIn(BaseModel):
    lines: list[OcetLineIn]
    deleted_line_ids: list[int] = Field(default_factory=list)


class RequestInputsIn(BaseModel):
    line_ids: list[int] = Field(min_length=1)


class RequestInputsOut(BaseModel):
    draft_ids: list[int]  # Orion drafts (one per input owner), status Draft - nothing is sent
    lines_requested: list[int]


class CompareRowOut(BaseModel):
    key: str  # line_key or category
    category: str
    description: str
    from_total: float
    to_total: float
    abs_change: float
    pct_change: float | None
    status: RowStatus
    from_yearly: list[YearAmount] = []
    to_yearly: list[YearAmount] = []


class CompareVersionRef(BaseModel):
    id: int
    version: int
    status: OcetStatus
    total: float


class OcetCompareOut(BaseModel):
    transition_id: str
    currency: str
    from_version: CompareVersionRef
    to_version: CompareVersionRef
    years: list[int]  # union of both versions' horizons (same estimate, so identical)
    rows: list[CompareRowOut]  # by line
    category_rows: list[CompareRowOut]  # by category
    from_total: float
    to_total: float
    total_abs: float
    total_pct: float | None
