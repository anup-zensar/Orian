"""Reminder engine: POST /reminders/run (BR-050/060), GET /reminders/status. M8."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.common import ErrorOut
from app.schemas.reminders import ReminderRunIn, ReminderRunOut, ReminderStatusOut

router = APIRouter(tags=["reminders"], dependencies=[Depends(get_current_user)])

_ERR = {403: {"model": ErrorOut}, 404: {"model": ErrorOut}, 422: {"model": ErrorOut}}


@router.post("/reminders/run", response_model=ReminderRunOut, responses=_ERR)
def run_reminder_engine(
    body: ReminderRunIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require(Perm.RUN_REMINDERS)),
) -> ReminderRunOut:
    """Run the reminder engine now (OR focal / Admin; 403 otherwise).

    Body optional: {rules: [ids]|None, transition_id: str|None}. 422 on an unknown rule id
    (not R1..R7); 404 on an unknown transition_id. Calls
    ``app.domain.reminders.run_reminders(db, user=user, rules=..., transition_id=...,
    triggered_by=user.id)`` then commits. Returns {run_id, at, created: {R1..R7: n},
    sent_autonomously, skipped_duplicates, drafts}. Disabled rules are skipped even if listed.
    Running twice in a row creates no duplicates (second run: created all 0, skipped_duplicates
    > 0)."""
    from app.domain import reminders  # imported late: orchestration module

    body = body or ReminderRunIn()
    result = reminders.run_reminders(
        db,
        user=user,
        rules=body.rules,
        transition_id=body.transition_id,
        triggered_by=user.id,
    )
    db.commit()
    return result


@router.get("/reminders/status", response_model=ReminderStatusOut, responses=_ERR)
def reminder_status(db: Session = Depends(get_db)) -> ReminderStatusOut:
    """Last run (latest ReminderRun by id, None if never) with counts per rule, the rules R1-R7
    (id, name, enabled, autonomous_eligible, params from ReminderRule, ordered by sort_order) and
    the ids of transitions with autonomous_mode true (drives the assistive/autonomous banner of
    screen 8.12). Any signed-in user. Read-only. Delegates to
    ``app.domain.reminders.reminder_status``."""
    from app.domain import reminders  # imported late: orchestration module

    return reminders.reminder_status(db)
