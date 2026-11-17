"""Reminder engine orchestration (BR-060, spec 7.8). Contract stub (M8b)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User
from app.schemas.reminders import ReminderRunOut, ReminderStatusOut


def run_reminders(
    db: Session,
    *,
    user: User | None,
    rules: list[str] | None = None,
    transition_id: str | None = None,
    triggered_by: str = "manual",
) -> ReminderRunOut:
    """Run the engine once. Does not commit (callers - router, scheduler - commit).

    1. Load enabled ReminderRule rows (filtered by ``rules`` when given; unknown ids -> BadRequest
       422; unknown ``transition_id`` -> NotFound 404) and Active transitions (optionally one).
    2. Build the facts of ``app.rules.reminders`` (TransitionFact, ItemFact, ActionFact, StepFact,
       OcetLineFact), RuleConfig(params=rule.params, today=clock.today()) and call
       evaluate_r1..r7. Never mutate business data.
    3. De-duplicate with ``rules.reminders.dedupe`` against OrionDraft.recipient_key of drafts
       created in the last 24 h (status Draft or Sent) - never a second open draft for the same
       rule + transition + recipient within 24 h. Count skipped.
    4. For each survivor generate text with ``get_ai_service(db).draft_message(kind, ctx)`` (R1 also
       fills the ``reminder_digest`` Adaptive Card from services/cards), then
       ``app.domain.drafts.create_draft(..., created_source="Workflow rule", rule_id=rule_id,
       action=candidate.action, related_ids=...)`` and set ``draft.recipient_key``. Recipients are
       resolved to emails via User.email.
    5. Autonomous: when the candidate is autonomous_eligible AND the rule's
       ReminderRule.autonomous_eligible AND Transition.autonomous_mode is true, the draft is sent
       immediately with the send_draft semantics (mail + Teams card via the mock services, status
       Sent, sent_at, sent_autonomously=True, audit actor_type "Workflow rule", sent_by None).
       Use a shared helper in app.domain.drafts if available, else replicate; the human-only
       ``send_draft`` is not called with a fake user. Eligible rules: R1, R2, R3 reminder only,
       R5. R3 escalation, R4 (carries action {"type": "request_approval", "gate": g}), R6, R7 are
       always left as Drafts for a human.
    6. Insert a ReminderRun {at, triggered_by (user id | "scheduler" | "manual"),
       created_counts {R1..R7: n} (all keys, counts of drafts created incl. autonomously sent),
       sent_autonomously} and an AuditEvent (entity "ReminderRun", action "run", actor = user or
       System/Workflow rule). Returns ReminderRunOut with drafts = created draft ids.

    Tests (AC-11): seeded data produces drafts per rule R1..R7 (one digest per owner per
    transition for R1); a second immediate run creates none (skipped_duplicates > 0); on a
    transition with autonomous_mode true R1/R2/R3(reminder)/R5 are Sent with sent_autonomously and
    audit actor_type "Workflow rule" while R3 escalation and R4/R6/R7 stay Draft; R4 draft action
    is request_approval with the decision gate and its Send (human) starts the chain; disabled
    rule produces nothing; ReminderRun counts equal what was created and show in GET
    /reminders/status."""
    raise NotImplementedError("M8")


def reminder_status(db: Session) -> ReminderStatusOut:
    """Build GET /reminders/status (last ReminderRun -> ReminderRunOut with drafts [] if unknown,
    rules ordered by sort_order, ids of transitions with autonomous_mode true)."""
    raise NotImplementedError("M8")
