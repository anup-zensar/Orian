"""Tiering and AI profile DTOs (spec §7.2 BR-011, §8.5, §6 TierAssessment / AIProfile)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import PersonRef


class TierCardOut(BaseModel):
    """Tier definition card (from reference.json tiers)."""

    tier: int
    name: str
    definition: str
    examples: str
    builder_persona: str


class TierProposeIn(BaseModel):
    """Inputs of the pure BR-011 rule. ``answers`` keys TQ1..TQ5 (missing key = false)."""

    audience: str | None = None  # Internal department | Enterprise | External
    write_actions: str | None = None  # No | Yes
    sensitive_data: str | None = None  # No | Personal sensitive | SOX / MC
    answers: dict[str, bool] = Field(default_factory=dict)


class TierProposalOut(BaseModel):
    proposed_tier: int
    rationale: list[str]
    tier: TierCardOut
    dimensions: list[str]  # the three tier dimensions shown next to the card


class TierSetIn(BaseModel):
    """PUT /transitions/{id}/tier body. The server computes the proposal from the transition's
    intake fields + ``answers``."""

    answers: dict[str, bool] = Field(default_factory=dict)


class TierConfirmIn(BaseModel):
    tier: int = Field(ge=1, le=4)
    reason: str | None = None  # required when tier differs from the proposal ("Change tier")


class TierAssessmentOut(BaseModel):
    transition_id: str
    answers: dict[str, bool]
    proposed_tier: int | None
    confirmed_tier: int | None
    status: str | None  # Proposed | Confirmed | None (not proposed yet)
    rationale: list[str]
    proposed_by: PersonRef | None
    confirmed_by_or_focal: PersonRef | None
    confirmed_by_irm: PersonRef | None
    confirmed_at: datetime | None
    change_reason: str | None
    tier: TierCardOut | None  # card of the confirmed tier, else the proposed one
    dimensions: list[str]
    reassembly: dict[str, int] | None = (
        None  # {added, excluded, restored, unchanged} if re-assembled
    )


class AIProfileIn(BaseModel):
    """All fields of spec §6 AIProfile (PUT replaces all)."""

    infrastructure_solution: str = ""
    agentic_framework: str = ""
    multi_agent_orchestration: bool = False
    number_of_users: str = ""
    agentic_workflows: str = ""
    models_used: str = ""
    data_sources: str = ""
    hosting: str = ""
    write_actions_detail: str = ""


class AIProfileOut(AIProfileIn):
    transition_id: str
    updated_at: datetime | None = None
