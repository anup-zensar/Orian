"""AI playbook eval metrics (spec §6 EvalTarget/EvalResult, §7.5, §8.7 j, FR-037)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EvalRowOut(BaseModel):
    metric_id: str  # EV-01
    metric: str
    target_text: str  # e.g. "<= 2%"
    operator: str | None  # >= <= < > == abs<=
    value: float | None
    unit: str | None
    evaluation: Literal[
        "auto", "manual"
    ]  # auto = pass computed from operator/value; manual = toggle
    result_number: float | None
    result_text: str | None
    passed: bool | None
    status: Literal["pass", "fail", "not evaluated"]
    evaluated_at: datetime | None
    source: str | None  # Manual | Imported (mock)


class EvalTableOut(BaseModel):
    tier: int | None
    targets_confirmed: bool
    banner: str  # "Targets currently identical for all tiers ..." when not confirmed, else ""
    rows: list[EvalRowOut]
    failed_count: int  # Technical blockers at SG4_ATD (BR-030)
    not_evaluated_count: int  # warning only


class EvalResultIn(BaseModel):
    metric_id: str = Field(max_length=50)
    value_number: float | None = None
    value_text: str | None = Field(default=None, max_length=4000)
    passed: bool | None = None  # manual metrics only; ignored for evaluation == auto
