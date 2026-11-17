"""Orion agent DTOs (spec §8.15, §9 "Orion agent"). Every Orion output is labelled "Orion agent" with an
AI badge in the UI (BR-050)."""

from __future__ import annotations

from pydantic import BaseModel


class InsightActionOut(BaseModel):
    """A button on an insight. M2: ``kind="link"`` navigates to ``href``. M8 adds proposal kinds that a
    permitted human accepts (BR-050)."""

    label: str
    kind: str = "link"
    href: str | None = None
    proposal_id: int | None = None


class InsightOut(BaseModel):
    id: str  # deterministic key, e.g. "TR-0001:critical-gap"
    text: str
    severity: str  # critical | warning | info | success
    transition_id: str | None = None
    actions: list[InsightActionOut] = []


class InsightsOut(BaseModel):
    scope: str  # dashboard | control-tower | transition
    scope_id: str | None = None
    generated_by: str = "Orion agent"
    insights: list[InsightOut]
