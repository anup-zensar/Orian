"""Reminder engine rules R1-R7 (BR-060, spec 7.8) as PURE functions (no DB, no clock reads).

Contract only (M8b); builders implement the bodies. The domain layer (``app.domain.reminders``)
gathers facts from the database, builds these dataclasses, calls ``evaluate_rN`` for each enabled
rule with thresholds from ``ReminderRule.params`` (wrapped in ``RuleConfig``), applies ``dedupe``
and turns each surviving ``ReminderCandidate`` into an OrionDraft (or an autonomous send).

Rules never send anything: they only describe a reminder. ``autonomous_eligible`` says whether the
candidate MAY be sent without a human click *when the transition is in autonomous mode*:
R1, R2, R3 (reminder only, never the escalation), R5. R4, R6, R7 and R3 escalations are NEVER
autonomous (``autonomous_eligible`` is always False for them).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

ReminderKind = Literal["Reminder", "Chaser", "Approval request", "Input request"]

RULE_IDS: tuple[str, ...] = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
# Rules that may be sent autonomously on autonomous transitions (spec 4 / 7.8).
AUTONOMOUS_RULES: frozenset[str] = frozenset({"R1", "R2", "R3", "R5"})
# R6 monitoring requirement items (once per transition).
R6_ITEM_IDS: tuple[str, ...] = tuple(f"FW-{n:03d}" for n in range(48, 55))  # FW-048..FW-054
DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "R1": {"days_before_decision": 14},
    "R2": {},
    "R3": {"reminder_after_days": 2, "escalate_after_days": 5},
    "R4": {},
    "R5": {"requested_for_days": 5},
    "R6": {},
    "R7": {},
}


@dataclass(frozen=True)
class RuleConfig:
    """Thresholds of one rule (``ReminderRule.params``); ``today`` is injected by the caller
    (``app.clock.today()``) so evaluation stays deterministic."""

    rule_id: str
    params: dict[str, Any] = field(default_factory=dict)
    today: date = date(2000, 1, 1)


@dataclass(frozen=True)
class TransitionFact:
    """What the rules need to know about one transition (only ones in status Active)."""

    transition_id: str
    name: str
    current_gate: str  # GATES code
    next_decision_gate: str | None  # first DECISION gate (SG4_ATD / SG6_ATO) at or after current
    next_decision_date: date | None
    or_focal_user_id: str
    architect_user_id: str | None
    autonomous_mode: bool
    first_approver_role: str | None  # for the R4 subject ("Ready for ATD - request OLM approval")
    open_approval_chain: bool  # a pending/in-progress ApprovalRequest exists for the decision gate
    support_model_exists: bool
    fw006_evidence_accepted: bool  # R7


@dataclass(frozen=True)
class ItemFact:
    """A TransitionItem row (applicable ones only)."""

    transition_id: str
    item_id: str  # playbook item id, e.g. "FW-012"
    title: str
    owner_user_id: str | None
    status: str  # raw status (Not started | In progress | Done | Covered | ...)
    first_due_gate: str  # gate by which the item is due (GATES code)
    gate_index: int  # position of first_due_gate in GATES (for "<= current gate" comparisons)
    done_or_covered: bool  # status in DONE_STATUSES or covered by evidence/condition


@dataclass(frozen=True)
class ActionFact:
    """An Action row."""

    transition_id: str
    action_id: str
    title: str
    owner_user_id: str | None
    due_date: date | None
    status: str  # Open | In progress | Done | Cancelled ...


@dataclass(frozen=True)
class StepFact:
    """A pending ApprovalStep (the chain's current, undecided step)."""

    transition_id: str
    approval_request_id: str
    step_id: str
    gate: str
    approver_user_id: str
    pending_since: date  # date the step became pending (request created / previous step decided)


@dataclass(frozen=True)
class OcetLineFact:
    """An OCET line whose input status is Requested."""

    transition_id: str
    line_id: str
    label: str
    input_owner_user_id: str | None
    requested_on: date | None


@dataclass(frozen=True)
class ReminderCandidate:
    """One reminder a rule wants to raise (not yet a draft)."""

    rule_id: str  # R1..R7
    transition_id: str
    recipient_user_id: str
    cc_user_ids: list[str]
    kind: ReminderKind
    subject_key: str  # stable key for de-dup (see ``dedupe_key``), e.g. "digest", "<step>:remind"
    related_ids: list[str]  # item/action/step/line ids (shown as source labels, spec 7.8)
    payload: dict[str, Any]  # context for AIService.draft_message(kind, ctx)
    autonomous_eligible: bool
    action: dict[str, Any] | None = None  # R4: {"type": "request_approval", "gate": <gate>}
    card: str | None = None  # "reminder_digest" for R1 (Adaptive Card template)


def dedupe_key(candidate: ReminderCandidate) -> str:
    """Return the OrionDraft.recipient_key for a candidate: ``f"{rule_id}|{transition_id}|
    {recipient_user_id}|{subject_key}"`` (<= 120 chars; truncate subject_key if needed)."""
    raise NotImplementedError("M8")


def evaluate_r1(
    config: RuleConfig,
    transitions: list[TransitionFact],
    items: list[ItemFact],
) -> list[ReminderCandidate]:
    """R1 - open items digest. For each transition with ``next_decision_date`` within
    ``params.days_before_decision`` days of ``config.today`` (days <= threshold; an overdue
    decision date also qualifies), collect OPEN items (not done_or_covered) due at the CURRENT
    gate or earlier (``gate_index <= index of current_gate``). Emit ONE candidate per
    (transition, owner) - a digest of that owner's items - kind "Reminder", cc OR focal (unless the
    owner is the focal), subject_key "digest", related_ids = item ids, card "reminder_digest",
    payload {transition_name, gate, decision_gate, decision_date, days_to_decision,
    items: [{id, title, due_gate}]}. autonomous_eligible True. Owners with no open items yield
    nothing; items without an owner go to the OR focal as recipient. Output order: by transition
    id, then recipient user id."""
    raise NotImplementedError("M8")


def evaluate_r2(
    config: RuleConfig,
    transitions: list[TransitionFact],
    actions: list[ActionFact],
) -> list[ReminderCandidate]:
    """R2 - overdue actions. One candidate per action with ``due_date < today`` and status not in
    (Done, Cancelled). Recipient = action owner (OR focal if none), cc = OR focal (unless same),
    kind "Chaser", subject_key = action_id, related_ids [action_id],
    payload {transition_name, action_id, title, due_date, days_overdue}.
    autonomous_eligible True."""
    raise NotImplementedError("M8")


def evaluate_r3(
    config: RuleConfig,
    transitions: list[TransitionFact],
    steps: list[StepFact],
) -> list[ReminderCandidate]:
    """R3 - approval steps pending too long. Params ``reminder_after_days`` and
    ``escalate_after_days``. For each pending step with age = today - pending_since:

    * age > escalate_after_days: ESCALATION to the OR focal about the approver (kind "Chaser",
      subject_key f"{step_id}:escalate", payload {..., escalation: True, approver_user_id}),
      autonomous_eligible ALWAYS False;
    * age > reminder_after_days: REMINDER to the approver (kind "Reminder", cc OR focal,
      subject_key f"{step_id}:remind", escalation False), autonomous_eligible True.

    When age exceeds the escalation threshold, emit BOTH the approver reminder and the escalation
    (dedupe removes the reminder if one is already open). related_ids [approval_request_id,
    step_id]; payload also has {transition_name, gate, approver_user_id, days_pending}."""
    raise NotImplementedError("M8")


def evaluate_r4(
    config: RuleConfig,
    transitions: list[TransitionFact],
    items: list[ItemFact],
) -> list[ReminderCandidate]:
    """R4 - ready for a decision gate. For each transition with a ``next_decision_gate`` where ALL
    applicable items with ``gate_index <= index of the decision gate`` are done_or_covered AND no
    ``open_approval_chain``: one candidate to the OR focal, kind "Approval request", subject_key
    f"ready:{gate}", payload {transition_name, gate, gate_label, first_approver_role,
    subject: "Ready for <gate short> - request <first approver role> approval?"} (e.g. "Ready for
    ATD - request OLM approval"), action {"type": "request_approval", "gate": <decision gate>} so
    the OR focal's Send starts the chain. autonomous_eligible ALWAYS False (approvals are never
    started autonomously)."""
    raise NotImplementedError("M8")


def evaluate_r5(
    config: RuleConfig,
    transitions: list[TransitionFact],
    lines: list[OcetLineFact],
) -> list[ReminderCandidate]:
    """R5 - stale OCET inputs. Lines with input status Requested for more than
    ``params.requested_for_days`` days (today - requested_on > threshold). ONE candidate per
    (transition, input owner), kind "Input request", cc OR focal, subject_key "ocet-inputs",
    related_ids = line ids, payload {transition_name, lines: [{id, label, days_requested}]}.
    autonomous_eligible True. Lines without an input owner go to the OR focal."""
    raise NotImplementedError("M8")


def evaluate_r6(
    config: RuleConfig,
    transitions: list[TransitionFact],
    items: list[ItemFact],
) -> list[ReminderCandidate]:
    """R6 - monitoring requirements. For each transition whose current_gate == "SG2" and which has
    an architect: one candidate to the Architect, kind "Reminder", cc OR focal, subject_key
    "monitoring-reqs", related_ids = R6_ITEM_IDS (FW-048..FW-054, only those present as items),
    payload {transition_name, items: [{id, title}]}. autonomous_eligible ALWAYS False. "Once per
    transition": the domain layer additionally skips the candidate when ANY OrionDraft with
    rule_id R6 already exists for the transition (any status except Discarded)."""
    raise NotImplementedError("M8")


def evaluate_r7(config: RuleConfig, transitions: list[TransitionFact]) -> list[ReminderCandidate]:
    """R7 - support model. Transitions where ``fw006_evidence_accepted`` and not
    ``support_model_exists``: one candidate to the OR focal, kind "Reminder", subject_key
    "support-model", payload {transition_name, subject: "Create support model now?"}, related_ids
    ["FW-006"], autonomous_eligible ALWAYS False."""
    raise NotImplementedError("M8")


def dedupe(
    candidates: list[ReminderCandidate],
    open_drafts_last_24h: set[str],
) -> tuple[list[ReminderCandidate], int]:
    """Drop duplicates (BR-060): a candidate is skipped when ``dedupe_key(candidate)`` is in
    ``open_drafts_last_24h`` (recipient_keys of drafts with status Draft or Sent created in the
    last 24 h) or when an earlier candidate in the same list has the same key. Order of the
    survivors is preserved. Returns (survivors, number_skipped)."""
    raise NotImplementedError("M8")
