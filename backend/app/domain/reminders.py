"""Reminder engine orchestration (BR-060, spec 7.8).

The pure rules live in ``app.rules.reminders``; this module gathers the facts, de-duplicates against
recent drafts, creates the OrionDrafts and - only for transitions in autonomous mode and only for
R1, R2, R3 (reminder) and R5 - sends them directly as a workflow rule. The engine never changes
business data (statuses, approvals, gate decisions): it only drafts or sends messages (BR-050).
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.config import get_settings
from app.domain import audit, cfg
from app.domain.approvals import chain_type_for_gate
from app.domain.notify import message_templates
from app.errors import BadRequest, Forbidden, NotFound
from app.models import (
    Action,
    ApprovalChainConfig,
    ApprovalRequest,
    Condition,
    Evidence,
    ExceptionRecord,
    OcetEstimate,
    OcetLine,
    OcetVersion,
    OrionDraft,
    OutboxMessage,
    ReminderRule,
    ReminderRun,
    SupportModel,
    Transition,
    TransitionItem,
    User,
)
from app.rules import reminders as rm
from app.rules.constants import (
    DECISION_GATES,
    DONE_STATUSES,
    GATE_ORDER,
    GATE_SHORT,
    GATES,
    NA_STATUSES,
)
from app.schemas.reminders import ReminderRuleOut, ReminderRunOut, ReminderStatusOut
from app.services.cards import render_card
from app.services.factory import get_ai_service, get_mail_service, get_notification_service

DEDUPE_WINDOW = timedelta(hours=24)
_SUPERSEDED_OCET = ("Superseded", "Rejected", "Approved")
_TAB = {  # where the recipient should land (workspace tabs, stable deep links)
    "R1": "assessment",
    "R2": "gaps",
    "R3": "gates",
    "R4": "gates",
    "R5": "ocet",
    "R6": "assessment",
    "R7": "support-model",
}


def _empty_counts() -> dict[str, int]:
    return {rule_id: 0 for rule_id in rm.RULE_IDS}


# --------------------------------------------------------------------------- facts


def _next_decision_gate(current_gate: str) -> str | None:
    start = GATE_ORDER.get(current_gate, 0)
    return next((g for g in GATES if g in DECISION_GATES and GATE_ORDER[g] >= start), None)


def _first_approver_role(db: Session, gate: str | None) -> str | None:
    if gate is None:
        return None
    config = db.get(ApprovalChainConfig, chain_type_for_gate(db, gate) or "")
    if config is None or not config.steps:
        return None
    return cfg.role_short_label(db, sorted(config.steps, key=lambda s: s["step"])[0]["role"])


def _transition_facts(db: Session, transitions: list[Transition]) -> list[rm.TransitionFact]:
    ids = [t.id for t in transitions]
    open_chain: set[tuple[str, str]] = {
        (r.transition_id, r.gate or "")
        for r in db.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.transition_id.in_(ids),
                ApprovalRequest.type.in_(list(cfg.gate_chain(db).values())),
                ApprovalRequest.status == "Pending",
            )
        ).all()
    }
    support_models = set(
        db.scalars(select(SupportModel.transition_id).where(SupportModel.transition_id.in_(ids)))
    )
    fw006 = set(
        db.scalars(
            select(Evidence.transition_id)
            .join(TransitionItem, TransitionItem.id == Evidence.transition_item_id)
            .where(
                Evidence.transition_id.in_(ids),
                Evidence.status == "Accepted",
                TransitionItem.playbook_item_id == "FW-006",
            )
        )
    )
    facts = []
    for t in transitions:
        gate = _next_decision_gate(t.current_gate)
        facts.append(
            rm.TransitionFact(
                transition_id=t.id,
                name=t.name,
                current_gate=t.current_gate,
                next_decision_gate=gate,
                next_decision_date=t.next_decision_date,
                or_focal_user_id=t.or_focal_user_id,
                architect_user_id=t.architect_user_id,
                autonomous_mode=bool(t.autonomous_mode),
                first_approver_role=_first_approver_role(db, gate),
                open_approval_chain=gate is not None and (t.id, gate) in open_chain,
                support_model_exists=t.id in support_models,
                fw006_evidence_accepted=t.id in fw006,
            )
        )
    return facts


def _item_facts(db: Session, transitions: list[Transition]) -> list[rm.ItemFact]:
    """Applicable items; "covered" = open condition due after the current gate or an approved
    exception (same meaning as the readiness check, A-09, A-33)."""
    by_id = {t.id: t for t in transitions}
    ids = list(by_id)
    cond_due: dict[int, int] = {}
    for c in db.scalars(
        select(Condition).where(
            Condition.transition_id.in_(ids),
            Condition.status == "Open",
            Condition.transition_item_id.is_not(None),
        )
    ).all():
        order = GATE_ORDER.get(c.due_gate, -1)
        key = int(c.transition_item_id)  # type: ignore[arg-type]
        cond_due[key] = max(cond_due.get(key, -1), order)
    excepted = set(
        db.scalars(
            select(ExceptionRecord.transition_item_id).where(
                ExceptionRecord.transition_id.in_(ids),
                ExceptionRecord.status == "Approved",
                ExceptionRecord.transition_item_id.is_not(None),
            )
        )
    )
    facts = []
    rows = db.scalars(
        select(TransitionItem)
        .where(TransitionItem.transition_id.in_(ids), TransitionItem.applicability == "Applies")
        .order_by(TransitionItem.transition_id, TransitionItem.playbook_item_id)
    ).all()
    for row in rows:
        current = GATE_ORDER.get(by_id[row.transition_id].current_gate, 0)
        covered = cond_due.get(row.id, -1) > current or row.id in excepted
        facts.append(
            rm.ItemFact(
                transition_id=row.transition_id,
                item_id=row.playbook_item_id,
                title=row.playbook_item.title,
                owner_user_id=row.owner_user_id,
                status=row.status,
                first_due_gate=row.due_gate,
                gate_index=GATE_ORDER.get(row.due_gate, 0),
                done_or_covered=row.status in DONE_STATUSES or row.status in NA_STATUSES or covered,
                category=row.playbook_item.category,
            )
        )
    return facts


def _action_facts(db: Session, ids: list[str]) -> list[rm.ActionFact]:
    return [
        rm.ActionFact(
            transition_id=a.transition_id,
            action_id=a.id,
            title=a.title,
            owner_user_id=a.owner_user_id,
            due_date=a.due_date,
            status=a.status,
        )
        for a in db.scalars(select(Action).where(Action.transition_id.in_(ids)).order_by(Action.id))
    ]


def _step_facts(db: Session, transitions: list[Transition]) -> list[rm.StepFact]:
    by_id = {t.id: t for t in transitions}
    mock_role = cfg.mock_approver(db)["mock_role"]
    facts = []
    for request in db.scalars(
        select(ApprovalRequest)
        .where(ApprovalRequest.transition_id.in_(list(by_id)), ApprovalRequest.status == "Pending")
        .order_by(ApprovalRequest.id)
    ).all():
        for step in request.steps:
            if step.status != "Pending":
                continue
            approver = step.approver_user_id
            if approver is None and step.role == mock_role:  # mocked step: IRM acts (demo)
                approver = by_id[request.transition_id].irm_user_id
            if approver is None:
                continue
            since = step.activated_at or request.created_at
            facts.append(
                rm.StepFact(
                    transition_id=request.transition_id,
                    approval_request_id=request.id,
                    step_id=str(step.id),
                    gate=request.gate or "",
                    approver_user_id=approver,
                    pending_since=since.date(),
                )
            )
    return facts


def _ocet_facts(db: Session, ids: list[str]) -> list[rm.OcetLineFact]:
    rows = db.execute(
        select(OcetLine, OcetEstimate.transition_id)
        .join(OcetVersion, OcetVersion.id == OcetLine.version_id)
        .join(OcetEstimate, OcetEstimate.id == OcetVersion.estimate_id)
        .where(
            OcetEstimate.transition_id.in_(ids),
            OcetLine.input_status == "Requested",
            OcetVersion.status.not_in(_SUPERSEDED_OCET),
        )
        .order_by(OcetEstimate.transition_id, OcetLine.sort_order)
    ).all()
    return [
        rm.OcetLineFact(
            transition_id=tid,
            line_id=str(line.id),
            label=(line.description or line.category or line.line_key).strip()[:120],
            input_owner_user_id=line.input_owner_user_id,
            requested_on=line.input_requested_at.date() if line.input_requested_at else None,
        )
        for line, tid in rows
    ]


# --------------------------------------------------------------------------- drafting


def _link(transition_id: str, rule_id: str, query: str = "") -> str:
    base = get_settings().app_base_url.rstrip("/")
    return f"{base}/transitions/{transition_id}/{_TAB[rule_id]}{query}"


def _message_context(
    c: rm.ReminderCandidate, t: Transition, users: dict[str, User]
) -> dict[str, Any]:
    """Context for ``AIService.draft_message`` (see services/mock/ai_messages.py)."""
    p = c.payload
    recipient = users.get(c.recipient_user_id)
    focal = users.get(t.or_focal_user_id)
    ctx: dict[str, Any] = {
        "transition_id": t.id,
        "transition_name": t.name,
        "gate_short": GATE_SHORT.get(t.current_gate, t.current_gate),
        "recipient_name": recipient.name if recipient else "",
        "or_focal_name": focal.name if focal else "",
        "deep_link": _link(t.id, c.rule_id),
    }
    if c.rule_id == "R1":
        # The date belongs to the AtD/ATO decision only when the transition is at (or past) that
        # stage; at a stage gate (SG0-SG3) it is the stage review of the current gate (spec 7.8).
        date_gate = (
            p["decision_gate"]
            if t.current_gate in DECISION_GATES or t.current_gate == "SG5_HYPERCARE"
            else t.current_gate
        )
        ctx["gate_short"] = GATE_SHORT.get(date_gate, date_gate)
        ctx["days"] = p["days_to_decision"]
        ctx["deep_link"] = _link(t.id, "R1", "?mine=1")
        ctx["items"] = [
            {
                "id": i["id"],
                "title": i["title"],
                "due_gate_short": GATE_SHORT.get(i["due_gate"], i["due_gate"]),
            }
            for i in p["items"]
        ]
    elif c.rule_id == "R2":
        ctx.update(action_title=p["title"], days_overdue=p["days_overdue"], due_date=p["due_date"])
    elif c.rule_id == "R3":
        approver = users.get(p["approver_user_id"])
        ctx.update(
            gate_short=GATE_SHORT.get(p["gate"], p["gate"] or "the gate"),
            days_pending=p["days_pending"],
            approver_name=approver.name if approver else "",
            escalation=bool(p["escalation"]),
            pending_step=not p["escalation"],
        )
    elif c.rule_id == "R5":
        ctx["items"] = [
            {
                "id": f"L{line['id']}",
                "title": f"{line['label']} (requested {line['days_requested']} days ago)",
                "deep_link": _link(t.id, "R5"),
            }
            for line in p["lines"]
        ]
    elif c.rule_id == "R6":
        ctx.update(monitoring=True, items=p["items"], gate_short="SG0-SG2")
    elif c.rule_id == "R7":
        ctx.update(support_model=True, subject=p["subject"])
    return ctx


def _digest_card(c: rm.ReminderCandidate, t: Transition, users: dict[str, User]) -> dict[str, Any]:
    p = c.payload
    owner = users.get(c.recipient_user_id)
    focal = users.get(t.or_focal_user_id)
    return render_card(
        "reminder_digest",
        {
            "count": len(p["items"]),
            "owner_name": owner.name if owner else "",
            "transition_name": t.name,
            "gate_short": GATE_SHORT.get(p["decision_gate"], p["decision_gate"]),
            "days": p["days_to_decision"],
            "items": [
                {"title": i["title"], "due_gate": GATE_SHORT.get(i["due_gate"], i["due_gate"])}
                for i in p["items"]
            ],
            "or_focal_name": focal.name if focal else "",
            "deep_link": _link(t.id, "R1", "?mine=1"),
        },
    )


def _send_autonomously(
    db: Session, draft: OrionDraft, card: dict[str, Any] | None, to_ids: list[str]
) -> list[int]:
    """Send a Draft as the workflow rule (mail + Teams card through the mock services) with the
    ``send_draft`` semantics: status Sent, sent_at, sent_autonomously, audit actor "Workflow rule",
    sent_by None. Used only for R1, R2, R3 (reminder) and R5 on autonomous transitions."""
    from app.domain import drafts  # another area; imported late

    to, cc = drafts.validate_addresses(draft.to or [], draft.cc or [])
    before = drafts._snap(draft)
    related = list(draft.related_ids or [])
    message_ids = [
        get_mail_service(db).send_mail(
            get_settings().orion_mailbox, to, cc, draft.subject, draft.body_html, related
        )
    ]
    db.flush()
    if to_ids:
        message_ids.append(
            get_notification_service(db).post_teams_card(
                to_ids, card or drafts._teams_card(draft), draft.subject, related
            )
        )
        db.flush()
    for message_id in message_ids:
        message = db.get(OutboxMessage, message_id)
        if message is not None:
            message.draft_id = draft.id
    draft.status = "Sent"
    draft.sent_by = None
    draft.sent_at = clock.now()
    draft.sent_autonomously = True
    audit.record(
        db,
        actor=None,
        actor_type="Workflow rule",
        entity="OrionDraft",
        entity_id=draft.id,
        action="sent",
        transition_id=draft.transition_id,
        before=before,
        after={**drafts._snap(draft), "sent_autonomously": True},
        note=f"Sent autonomously by rule {draft.rule_id} (autonomous mode); no human click",
    )
    return message_ids


# --------------------------------------------------------------------------- run


def run_reminders(
    db: Session,
    *,
    user: User | None,
    rules: list[str] | None = None,  # noqa: A002 - public contract name
    transition_id: str | None = None,
    triggered_by: str = "manual",
    only_transition_ids: Collection[str] | None = None,
) -> ReminderRunOut:
    """Run the engine once (see the module docstring). Does not commit.

    ``only_transition_ids`` limits the run to those transitions (an OR focal runs only for the
    transitions assigned to them). Unknown rule ids -> 422; unknown ``transition_id`` -> 404."""
    from app.domain import drafts  # another area; imported late

    if user is not None and user.role == "OR_FOCAL":
        # An OR focal runs the engine only for the transitions assigned to them (R-01, AC-11).
        own = set(
            db.scalars(select(Transition.id).where(Transition.or_focal_user_id == user.id)).all()
        )
        if transition_id is not None and transition_id not in own:
            raise Forbidden(
                "Only the OR focal of the transition or an Admin can run reminders for it",
                [f"{transition_id} is not one of your transitions"],
            )
        only_transition_ids = own if only_transition_ids is None else own & set(only_transition_ids)

    rule_rows = list(db.scalars(select(ReminderRule).order_by(ReminderRule.sort_order)).all())
    known = {r.id for r in rule_rows} | set(rm.RULE_IDS)
    if rules:
        unknown = sorted({r for r in rules if r not in known})
        if unknown:
            raise BadRequest(
                "Unknown reminder rule", [f"{r} is not a rule (R1..R7)" for r in unknown]
            )
    wanted = set(rules) if rules else None
    enabled = {r.id: r for r in rule_rows if r.enabled and (wanted is None or r.id in wanted)}

    query = select(Transition).where(Transition.status == "Active").order_by(Transition.id)
    if transition_id is not None:
        if db.get(Transition, transition_id) is None:
            raise NotFound(f"Transition {transition_id} not found")
        query = query.where(Transition.id == transition_id)
    if only_transition_ids is not None:
        query = query.where(Transition.id.in_(list(only_transition_ids)))
    transitions = list(db.scalars(query).all())
    by_id = {t.id: t for t in transitions}
    users = {u.id: u for u in db.scalars(select(User)).all()}
    today = clock.today()

    candidates: list[Any] = []
    if transitions and enabled:
        ids = list(by_id)
        tfacts = _transition_facts(db, transitions)
        ifacts = _item_facts(db, transitions) if enabled.keys() & {"R1", "R4", "R6"} else []

        def rule_config(rid: str) -> Any:
            return rm.RuleConfig(rule_id=rid, params=dict(enabled[rid].params or {}), today=today)

        if "R1" in enabled:
            candidates += rm.evaluate_r1(rule_config("R1"), tfacts, ifacts)
        if "R2" in enabled:
            candidates += rm.evaluate_r2(rule_config("R2"), tfacts, _action_facts(db, ids))
        if "R3" in enabled:
            candidates += rm.evaluate_r3(rule_config("R3"), tfacts, _step_facts(db, transitions))
        if "R4" in enabled:
            candidates += rm.evaluate_r4(rule_config("R4"), tfacts, ifacts)
        if "R5" in enabled:
            candidates += rm.evaluate_r5(rule_config("R5"), tfacts, _ocet_facts(db, ids))
        if "R6" in enabled:
            candidates += rm.evaluate_r6(rule_config("R6"), tfacts, ifacts)
        if "R7" in enabled:
            candidates += rm.evaluate_r7(rule_config("R7"), tfacts)

    skipped = 0
    if candidates:
        # R6 once per transition: any non-discarded R6 draft blocks a new one.
        had_r6 = set(
            db.scalars(
                select(OrionDraft.transition_id).where(
                    OrionDraft.rule_id == "R6", OrionDraft.status != "Discarded"
                )
            )
        )
        kept = [c for c in candidates if not (c.rule_id == "R6" and c.transition_id in had_r6)]
        skipped += len(candidates) - len(kept)
        recent_cut: datetime = clock.now() - DEDUPE_WINDOW
        recent = set(
            db.scalars(
                select(OrionDraft.recipient_key).where(
                    OrionDraft.recipient_key.is_not(None),
                    OrionDraft.status.in_(("Draft", "Sent")),
                    OrionDraft.created_at >= recent_cut,
                )
            )
        )
        candidates, dup = rm.dedupe(kept, recent)
        skipped += dup

    created = _empty_counts()
    sent_auto = 0
    draft_ids: list[int] = []
    for c in candidates:
        t = by_id[c.transition_id]
        recipient = users.get(c.recipient_user_id)
        if recipient is None:
            continue
        cc = [users[u].email for u in c.cc_user_ids if u in users]
        to = [recipient.email]
        if c.rule_id == "R4":
            # The message IS the approval request (spec 7.8, storyline step 9): To = first
            # approver, Cc = OR focal; it stays in the OR focal's queue (only she may send it).
            to, cc, text = drafts.approval_request_message(db, t, c.payload["gate"], recipient)
            text = {**text, "subject": c.payload["subject"]}
        else:
            ctx = {**_message_context(c, t, users), "templates": message_templates(db)}
            text = get_ai_service().draft_message(c.kind, ctx)
        draft = drafts.create_draft(
            db,
            kind=c.kind,
            transition=t,
            to=to,
            cc=cc,
            subject=text["subject"],
            body_html=text["body_html"],
            created_source="Workflow rule",
            rule_id=c.rule_id,
            action=c.action,
            related_ids=[t.id, *c.related_ids],
        )
        draft.recipient_key = rm.dedupe_key(c)
        created[c.rule_id] += 1
        draft_ids.append(draft.id)
        rule_row = enabled[c.rule_id]
        if c.autonomous_eligible and rule_row.autonomous_eligible and t.autonomous_mode:
            card = _digest_card(c, t, users) if c.card == "reminder_digest" else None
            to_ids = [u.id for u in users.values() if u.email in {recipient.email, *cc}]
            _send_autonomously(db, draft, card, to_ids)
            sent_auto += 1

    run = ReminderRun(
        at=clock.now(),
        triggered_by=(user.id if user is not None else triggered_by)[:20],
        created_counts=created,
        sent_autonomously=sent_auto,
    )
    db.add(run)
    db.flush()
    total = sum(created.values())
    audit.record(
        db,
        actor=user,
        actor_type="Human" if user is not None else "System",
        entity="ReminderRun",
        entity_id=run.id,
        action="run",
        after={"created": created, "sent_autonomously": sent_auto, "skipped_duplicates": skipped},
        note=(
            f"Reminder engine ran ({triggered_by}): {total} drafted, {sent_auto} sent "
            f"autonomously, {skipped} duplicates skipped"
        ),
    )
    return ReminderRunOut(
        run_id=run.id,
        at=run.at,
        created=created,
        sent_autonomously=sent_auto,
        skipped_duplicates=skipped,
        drafts=draft_ids,
    )


def _run_out(run: ReminderRun) -> ReminderRunOut:
    counts = {**_empty_counts(), **(run.created_counts or {})}
    return ReminderRunOut(
        run_id=run.id,
        at=run.at,
        created=counts,
        sent_autonomously=run.sent_autonomously,
        skipped_duplicates=0,
        drafts=[],
    )


def reminder_status(db: Session) -> ReminderStatusOut:
    """Build GET /reminders/status (last ReminderRun, rules by sort_order, autonomous transitions)."""
    last = db.scalars(select(ReminderRun).order_by(ReminderRun.id.desc()).limit(1)).first()
    rule_rows = db.scalars(select(ReminderRule).order_by(ReminderRule.sort_order)).all()
    autonomous = db.scalars(
        select(Transition.id)
        .where(Transition.autonomous_mode.is_(True), Transition.status == "Active")
        .order_by(Transition.id)
    ).all()
    return ReminderStatusOut(
        last_run=_run_out(last) if last else None,
        rules=[
            ReminderRuleOut(
                id=r.id,
                name=r.name,
                enabled=r.enabled,
                autonomous_eligible=r.autonomous_eligible,
                params=dict(r.params or {}),
            )
            for r in rule_rows
        ],
        autonomous_transitions=list(autonomous),
    )
