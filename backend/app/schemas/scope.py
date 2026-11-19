"""Scope page DTOs (spec §8.6 FR-022)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ScopeRowOut(BaseModel):
    id: str  # playbook item id (GCC-01, ALL-02 ...)
    requirement: str
    type: Literal["Mandatory", "Portfolio", "Common"]
    gate: str  # gate code
    gate_short: str
    owner_hint: str
    lens: str
    lens_is_suggested: bool
    applies: Literal["Yes", "No", "To confirm"]
    locked: bool  # mandatory -> locked Yes
    reason: str | None = None


class ScopeCountsOut(BaseModel):
    framework: int
    ai_applicable: int
    ai_excluded: int
    golden_set_applies: int
    golden_set_to_confirm: int
    common: int
    other: int = 0  # applicable items of checklists an Admin added
    total: int  # total applicable items


class TierBannerOut(BaseModel):
    tier: int | None
    status: str | None  # Proposed | Confirmed
    text: str  # e.g. "Checklist based on proposed Tier 2 - confirm tier to finalise"


class RecommendationOut(BaseModel):
    """Orion agent recommendation for a To-confirm row (never applied automatically)."""

    item_id: str
    recommendation: Literal["Yes", "No"]
    reason: str


class ScopeOut(BaseModel):
    transition_id: str
    portfolio: str
    focus_areas: list[str]
    golden_set: list[ScopeRowOut]
    common: list[ScopeRowOut]
    counts: ScopeCountsOut
    tier_banner: TierBannerOut | None  # None for non-AI flavours
    recommendations: list[RecommendationOut]  # labelled "Orion agent" in the UI
    launched: bool


class ScopeDecisionIn(BaseModel):
    item_id: str = Field(max_length=50)
    applies: Literal["Yes", "No", "To confirm"]
    reason: str | None = Field(default=None, max_length=4000)


class ScopeUpdateIn(BaseModel):
    decisions: list[ScopeDecisionIn] = Field(max_length=2000)
    source: Literal["human", "orion_recommendation"] = "human"


class LaunchOut(BaseModel):
    transition_id: str
    counts: dict[str, int]  # BR-010 summarize_counts
    redirect: str = Field(description='"/transitions/<id>/assessment"')
