"""Reminder engine DTOs (spec 8.12, 8.16, 9; BR-060)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReminderRunIn(BaseModel):
    """Optional body of POST /reminders/run."""

    rules: list[str] | None = Field(
        default=None, description="Only evaluate these rule ids (R1..R7); None = all enabled"
    )
    transition_id: str | None = Field(
        default=None, description="Only this transition; None = all active transitions"
    )


class ReminderRunOut(BaseModel):
    run_id: int
    at: datetime
    created: dict[str, int]  # {"R1": n, ..., "R7": n}; every key present (0 when none)
    sent_autonomously: int
    skipped_duplicates: int = 0
    drafts: list[int] = []  # ids of the OrionDrafts created (Draft and autonomously Sent)


class ReminderRuleOut(BaseModel):
    id: str  # R1..R7
    name: str
    enabled: bool
    autonomous_eligible: bool
    params: dict[str, Any]


class ReminderStatusOut(BaseModel):
    last_run: ReminderRunOut | None
    rules: list[ReminderRuleOut]
    autonomous_transitions: list[str]  # ids of transitions with autonomous_mode true
