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

from app.rules.constants import GATE_ORDER, GATE_SHORT

_GATE_LABEL = {"SG4_ATD": "Authority to Deploy", "SG6_ATO": "Authority to Operate"}

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


def _cc(t: TransitionFact, recipient: str) -> list[str]:
    return [] if recipient == t.or_focal_user_id else [t.or_focal_user_id]


def dedupe_key(candidate: ReminderCandidate) -> str:
    """Return the OrionDraft.recipient_key for a candidate: ``f"{rule_id}|{transition_id}|
    {recipient_user_id}|{subject_key}"`` (<= 120 chars; truncate subject_key if needed)."""
    key = f"{candidate.rule_id}|{candidate.transition_id}|{candidate.recipient_user_id}|"
    return key + candidate.subject_key[: max(0, 120 - len(key))]


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
    gate_index = {t.transition_id: GATE_ORDER.get(t.current_gate, 0) for t in transitions}
    out: list[ReminderCandidate] = []
    for t in sorted(transitions, key=lambda x: x.transition_id):
        if t.next_decision_date is None or t.next_decision_gate is None:
            continue
        days = (t.next_decision_date - config.today).days
        if days > int(config.params.get("days_before_decision", 14)):
            continue
        by_owner: dict[str, list[ItemFact]] = {}
        for i in items:
            if (
                i.transition_id == t.transition_id
                and not i.done_or_covered
                and i.gate_index <= gate_index[t.transition_id]
            ):
                by_owner.setdefault(i.owner_user_id or t.or_focal_user_id, []).append(i)
        for owner in sorted(by_owner):
            mine = by_owner[owner]
            out.append(
                ReminderCandidate(
                    rule_id="R1",
                    transition_id=t.transition_id,
                    recipient_user_id=owner,
                    cc_user_ids=_cc(t, owner),
                    kind="Reminder",
                    subject_key="digest",
                    related_ids=[i.item_id for i in mine],
                    payload={
                        "transition_name": t.name,
                        "gate": t.current_gate,
                        "decision_gate": t.next_decision_gate,
                        "decision_date": t.next_decision_date.isoformat(),
                        "days_to_decision": days,
                        "items": [
                            {"id": i.item_id, "title": i.title, "due_gate": i.first_due_gate}
                            for i in mine
                        ],
                    },
                    autonomous_eligible=True,
                    card="reminder_digest",
                )
            )
    return out


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
    by_id = {t.transition_id: t for t in transitions}
    out: list[ReminderCandidate] = []
    for a in sorted(actions, key=lambda x: (x.transition_id, x.action_id)):
        t = by_id.get(a.transition_id)
        if t is None or a.due_date is None or a.due_date >= config.today:
            continue
        if a.status in ("Done", "Cancelled"):
            continue
        owner = a.owner_user_id or t.or_focal_user_id
        out.append(
            ReminderCandidate(
                rule_id="R2",
                transition_id=t.transition_id,
                recipient_user_id=owner,
                cc_user_ids=_cc(t, owner),
                kind="Chaser",
                subject_key=a.action_id,
                related_ids=[a.action_id],
                payload={
                    "transition_name": t.name,
                    "action_id": a.action_id,
                    "title": a.title,
                    "due_date": a.due_date.isoformat(),
                    "days_overdue": (config.today - a.due_date).days,
                },
                autonomous_eligible=True,
            )
        )
    return out


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
    by_id = {t.transition_id: t for t in transitions}
    remind_after = int(config.params.get("reminder_after_days", 2))
    escalate_after = int(config.params.get("escalate_after_days", 5))
    out: list[ReminderCandidate] = []
    for s in sorted(steps, key=lambda x: (x.transition_id, x.approval_request_id, x.step_id)):
        t = by_id.get(s.transition_id)
        if t is None:
            continue
        age = (config.today - s.pending_since).days
        payload = {
            "transition_name": t.name,
            "gate": s.gate,
            "approver_user_id": s.approver_user_id,
            "days_pending": age,
        }
        related = [s.approval_request_id, s.step_id]
        if age > remind_after:
            out.append(
                ReminderCandidate(
                    rule_id="R3",
                    transition_id=t.transition_id,
                    recipient_user_id=s.approver_user_id,
                    cc_user_ids=_cc(t, s.approver_user_id),
                    kind="Reminder",
                    subject_key=f"{s.step_id}:remind",
                    related_ids=related,
                    payload={**payload, "escalation": False},
                    autonomous_eligible=True,
                )
            )
        if age > escalate_after:
            out.append(
                ReminderCandidate(
                    rule_id="R3",
                    transition_id=t.transition_id,
                    recipient_user_id=t.or_focal_user_id,
                    cc_user_ids=[],
                    kind="Chaser",
                    subject_key=f"{s.step_id}:escalate",
                    related_ids=related,
                    payload={**payload, "escalation": True},
                    autonomous_eligible=False,
                )
            )
    return out


def evaluate_r4(
    config: RuleConfig,
    transitions: list[TransitionFact],
    items: list[ItemFact],
) -> list[ReminderCandidate]:
    """R4 - ready for a decision gate. For each transition with a ``next_decision_gate`` where ALL
    applicable items with ``gate_index <= index of the decision gate`` are done_or_covered AND no
    ``open_approval_chain`` (and there is at least one such item): one candidate to the OR focal, kind "Approval request", subject_key
    f"ready:{gate}", payload {transition_name, gate, gate_label, first_approver_role,
    subject: "Ready for <gate short> - request <first approver role> approval"} (e.g. "Ready for
    ATD - request OLM approval"), action {"type": "request_approval", "gate": <decision gate>} so
    the OR focal's Send starts the chain. autonomous_eligible ALWAYS False (approvals are never
    started autonomously)."""
    out: list[ReminderCandidate] = []
    for t in sorted(transitions, key=lambda x: x.transition_id):
        gate = t.next_decision_gate
        if gate is None or t.open_approval_chain:
            continue
        limit = GATE_ORDER[gate]
        scoped = [i for i in items if i.transition_id == t.transition_id and i.gate_index <= limit]
        if not scoped or any(not i.done_or_covered for i in scoped):
            continue  # no applicable items = the assessment is not launched: nothing is "ready"
        short = GATE_SHORT.get(gate, gate)
        role = t.first_approver_role or "approver"
        out.append(
            ReminderCandidate(
                rule_id="R4",
                transition_id=t.transition_id,
                recipient_user_id=t.or_focal_user_id,
                cc_user_ids=[],
                kind="Approval request",
                subject_key=f"ready:{gate}",
                related_ids=[t.transition_id],
                payload={
                    "transition_name": t.name,
                    "gate": gate,
                    "gate_label": _GATE_LABEL.get(gate, short),
                    "first_approver_role": role,
                    "subject": f"Ready for {short} - request {role} approval",
                },
                autonomous_eligible=False,
                action={"type": "request_approval", "gate": gate},
            )
        )
    return out


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
    by_id = {t.transition_id: t for t in transitions}
    threshold = int(config.params.get("requested_for_days", 5))
    grouped: dict[tuple[str, str], list[tuple[OcetLineFact, int]]] = {}
    for line in lines:
        t = by_id.get(line.transition_id)
        if t is None or line.requested_on is None:
            continue
        waited = (config.today - line.requested_on).days
        if waited <= threshold:
            continue
        owner = line.input_owner_user_id or t.or_focal_user_id
        grouped.setdefault((t.transition_id, owner), []).append((line, waited))
    out: list[ReminderCandidate] = []
    for (tid, owner), mine in sorted(grouped.items()):
        t = by_id[tid]
        out.append(
            ReminderCandidate(
                rule_id="R5",
                transition_id=tid,
                recipient_user_id=owner,
                cc_user_ids=_cc(t, owner),
                kind="Input request",
                subject_key="ocet-inputs",
                related_ids=[ln.line_id for ln, _ in mine],
                payload={
                    "transition_name": t.name,
                    "lines": [
                        {"id": ln.line_id, "label": ln.label, "days_requested": w} for ln, w in mine
                    ],
                },
                autonomous_eligible=True,
            )
        )
    return out


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
    present: dict[str, dict[str, str]] = {}
    for i in items:
        if i.item_id in R6_ITEM_IDS:
            present.setdefault(i.transition_id, {})[i.item_id] = i.title
    out: list[ReminderCandidate] = []
    for t in sorted(transitions, key=lambda x: x.transition_id):
        if t.current_gate != "SG2" or not t.architect_user_id:
            continue
        mine = present.get(t.transition_id, {})
        ids = [i for i in R6_ITEM_IDS if i in mine]
        out.append(
            ReminderCandidate(
                rule_id="R6",
                transition_id=t.transition_id,
                recipient_user_id=t.architect_user_id,
                cc_user_ids=_cc(t, t.architect_user_id),
                kind="Reminder",
                subject_key="monitoring-reqs",
                related_ids=ids,
                payload={
                    "transition_name": t.name,
                    "items": [{"id": i, "title": mine[i]} for i in ids],
                },
                autonomous_eligible=False,
            )
        )
    return out


def evaluate_r7(config: RuleConfig, transitions: list[TransitionFact]) -> list[ReminderCandidate]:
    """R7 - support model. Transitions where ``fw006_evidence_accepted`` and not
    ``support_model_exists``: one candidate to the OR focal, kind "Reminder", subject_key
    "support-model", payload {transition_name, subject: "Create support model now?"}, related_ids
    ["FW-006"], autonomous_eligible ALWAYS False."""
    return [
        ReminderCandidate(
            rule_id="R7",
            transition_id=t.transition_id,
            recipient_user_id=t.or_focal_user_id,
            cc_user_ids=[],
            kind="Reminder",
            subject_key="support-model",
            related_ids=["FW-006"],
            payload={"transition_name": t.name, "subject": "Create support model now?"},
            autonomous_eligible=False,
        )
        for t in sorted(transitions, key=lambda x: x.transition_id)
        if t.fw006_evidence_accepted and not t.support_model_exists
    ]


def dedupe(
    candidates: list[ReminderCandidate],
    open_drafts_last_24h: set[str],
) -> tuple[list[ReminderCandidate], int]:
    """Drop duplicates (BR-060): a candidate is skipped when ``dedupe_key(candidate)`` is in
    ``open_drafts_last_24h`` (recipient_keys of drafts with status Draft or Sent created in the
    last 24 h) or when an earlier candidate in the same list has the same key. Order of the
    survivors is preserved. Returns (survivors, number_skipped)."""
    seen = set(open_drafts_last_24h)
    survivors: list[ReminderCandidate] = []
    for candidate in candidates:
        key = dedupe_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        survivors.append(candidate)
    return survivors, len(candidates) - len(survivors)
