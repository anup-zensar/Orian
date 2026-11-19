"""Readiness check assembly (FR-050, spec 8.9). READ-ONLY: no writes, no audit.

``load_gate_inputs`` builds the pure :class:`app.rules.gates.GateContext` from the database; it is
shared by the readiness check, the gate actions (stage review / decision / request approval) and the
gates overview, so the verdict shown and the rule that is enforced can never disagree (BR-040).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.domain import cfg
from app.models import (
    Action,
    ApprovalRequest,
    Condition,
    EvalResult,
    ExceptionRecord,
    HypercareDefect,
    OcetEstimate,
    SupportModel,
    Transition,
    TransitionItem,
    User,
)
from app.permissions import DENIAL_REASONS, Perm, has_perm
from app.rules import gates as rules
from app.rules.constants import (
    APPLIES,
    DONE_STATUSES,
    GATE_ORDER,
    GATE_OUTCOMES,
    GATE_SHORT,
    GATE_TYPE,
    GATES,
    LENSES,
    is_open_status,
)
from app.rules.readiness import ReadinessItem, compute_readiness
from app.schemas.common import LensValues, PersonRef
from app.schemas.gates import (
    ApprovalStepOut,
    BlockingGroup,
    CarriedItemOut,
    DecisionOption,
    FailedEvalOut,
    GateApprovalOut,
    GateItemRef,
    OpenConditionOut,
    PendingExceptionOut,
    ReadinessCheckOut,
    RecommendedAction,
)
from app.services.factory import get_ai_service

DECISION_CHAIN_TYPE = {"SG4_ATD": "AtD", "SG6_ATO": "AtO"}
_NARRATIVE_TOP = 3


@dataclass
class GateInputs:
    """Everything loaded for one (transition, gate): the rule context plus display details."""

    ctx: rules.GateContext
    items: dict[str, TransitionItem]  # playbook item id -> row (all of the transition's items)
    titles: dict[str, str]
    conditions: list[Condition]
    exceptions: list[ExceptionRecord]
    chain: ApprovalRequest | None
    ocet_status: str | None
    support_model_status: str | None
    unevaluated_evals: int
    users: dict[str, User]
    lens_pct: dict[str, int] = field(default_factory=dict)


def _result_text(result: EvalResult, unit: str | None) -> str:
    if result.value_number is not None:
        return f"{result.value_number:g}{unit or ''}"
    return result.value_text or ""


def latest_chain(db: Session, transition_id: str, gate: str) -> ApprovalRequest | None:
    """Latest AtD / AtO approval request of the gate (highest APR id)."""
    chain_type = DECISION_CHAIN_TYPE.get(gate)
    if chain_type is None:
        return None
    return db.scalars(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.transition_id == transition_id,
            ApprovalRequest.type == chain_type,
            ApprovalRequest.gate == gate,
        )
        .order_by(ApprovalRequest.id.desc())
    ).first()


def _evals(db: Session, transition: Transition, gate: str) -> tuple[list[rules.FailedEval], int]:
    """(failed evals, unevaluated metric count) for AI flavours; failed only listed at AtD."""
    from app.domain import eval as eval_domain  # local import: eval imports records/access

    if not eval_domain.has_eval_metrics(db, transition) or transition.risk_tier is None:
        return [], 0
    # Always the CURRENT tier's targets and the shared pass rule (BE#5): a tier change or an Admin
    # edit of the targets changes the blockers without re-importing results.
    targets = eval_domain.targets_for_transition(db, transition)
    results: dict[str, EvalResult] = {}
    for r in db.scalars(
        select(EvalResult).where(EvalResult.transition_id == transition.id).order_by(EvalResult.id)
    ).all():
        results[r.metric_id] = r
    failed: list[rules.FailedEval] = []
    unevaluated = 0
    for t in targets:
        r = results.get(t.metric_id)
        passed = eval_domain.pass_state(t, r)
        if r is None or passed is None:
            unevaluated += 1
        elif passed is False and gate == "SG4_ATD":
            failed.append(
                rules.FailedEval(
                    metric_id=t.metric_id,
                    metric=t.metric,
                    result=_result_text(r, t.unit),
                    target_text=t.target_text,
                )
            )
    return failed, unevaluated


def load_gate_inputs(db: Session, transition: Transition, gate: str) -> GateInputs:
    """Load the rule context for ``gate`` (a valid gate code)."""
    from app.domain import eval as eval_domain  # local imports: they import records / access
    from app.domain import scope as scope_domain

    gate_order = GATE_ORDER[gate]
    users = {u.id: u for u in db.scalars(select(User)).all()}
    rows = db.scalars(
        select(TransitionItem)
        .where(TransitionItem.transition_id == transition.id)
        .order_by(TransitionItem.id)
    ).all()
    by_pid = {r.playbook_item_id: r for r in rows}
    titles = {r.playbook_item_id: r.playbook_item.title for r in rows}

    conditions = list(
        db.scalars(
            select(Condition).where(Condition.transition_id == transition.id).order_by(Condition.id)
        ).all()
    )
    exceptions = list(
        db.scalars(
            select(ExceptionRecord)
            .where(ExceptionRecord.transition_id == transition.id)
            .order_by(ExceptionRecord.ref)
        ).all()
    )
    cond_after: set[int] = {
        c.transition_item_id
        for c in conditions
        if c.status == "Open"
        and c.transition_item_id is not None
        and GATE_ORDER.get(c.due_gate, -1) > gate_order
    }
    approved: set[int] = {
        e.transition_item_id
        for e in exceptions
        if e.status == "Approved" and e.transition_item_id is not None
    }
    pending: dict[int, str] = {
        e.transition_item_id: e.ref
        for e in exceptions
        if e.status.startswith("Pending") and e.transition_item_id is not None
    }

    facts: list[rules.GateItemFact] = []
    readiness_items: list[ReadinessItem] = []
    for r in rows:
        if r.applicability != APPLIES or GATE_ORDER.get(r.due_gate, 99) > gate_order:
            continue
        lens = r.playbook_item.lens
        covered_cond = r.id in cond_after
        covered_exc = r.id in approved
        facts.append(
            rules.GateItemFact(
                item_id=r.playbook_item_id,
                lens=lens,
                due_gate=r.due_gate,
                status=r.status,
                gap_severity=r.gap_severity,
                covered_by_condition=covered_cond,
                under_approved_exception=covered_exc,
                under_pending_exception=r.id in pending and not covered_exc,
                linked_module=r.linked_module,
                title=r.playbook_item.title,
                exception_ref=pending.get(r.id),
            )
        )
        readiness_items.append(
            ReadinessItem(
                lens=lens,
                due_gate=r.due_gate,
                applicability=r.applicability,
                status=r.status,
                gap_severity=r.gap_severity,
                covered=covered_cond or covered_exc,
            )
        )
    lens_pct = compute_readiness(readiness_items, gate, cfg.critical_severity(db)).lens_pct

    # The tier gate check and the AtD eval check follow the project-type switches, not its name.
    has_evals = eval_domain.has_eval_metrics(db, transition)
    ai = has_evals or scope_domain.requires_tiering(db, transition.project_type)
    failed, unevaluated = _evals(db, transition, gate) if has_evals else ([], 0)

    estimate = db.scalars(
        select(OcetEstimate).where(OcetEstimate.transition_id == transition.id)
    ).first()
    ocet_status: str | None = None
    if estimate is not None and estimate.versions:
        latest = max(estimate.versions, key=lambda v: v.version)
        ocet_status = f"{latest.status} v{latest.version}"
    ocet_approved = ocet_status is not None and ocet_status.startswith("Approved")
    sm = db.scalars(
        select(SupportModel)
        .where(SupportModel.transition_id == transition.id)
        .order_by(SupportModel.version.desc(), SupportModel.id.desc())
    ).first()
    sm_status = sm.status if sm is not None else None

    chain = latest_chain(db, transition.id, gate)
    pending_step = None
    if chain is not None and chain.status == "Pending":
        pending_step = next((s.label for s in chain.steps if s.status == "Pending"), None)

    open_due = [
        c.id
        for c in conditions
        if c.status == "Open" and GATE_ORDER.get(c.due_gate, 99) <= gate_order
    ]
    extra: dict[str, Any] = {}
    if gate == "SG6_ATO":
        defects = db.scalars(
            select(HypercareDefect).where(HypercareDefect.transition_id == transition.id)
        ).all()
        extra["open_p1_p2"] = sum(
            1 for d in defects if d.status == "Open" and d.priority in ("P1", "P2")
        )
        extra["tracker_in_place"] = bool(defects) or transition.hypercare_no_defects_confirmed
    if gate in ("SG6_ATO", "CLOSURE"):
        extra["atd_conditions_open"] = sum(
            1
            for c in conditions
            if c.status == "Open"
            and c.set_at_gate == "SG4_ATD"
            and GATE_ORDER.get(c.due_gate, 99) <= gate_order
        )
        extra["ocet_approved"] = ocet_approved
        extra["support_model_agreed"] = sm_status == "Agreed"
    if gate == "CLOSURE":
        extra["open_actions"] = len(
            db.scalars(
                select(Action.id).where(
                    Action.transition_id == transition.id,
                    Action.status.in_(("Open", "In progress")),
                )
            ).all()
        )
        extra["open_defects"] = len(
            db.scalars(
                select(HypercareDefect.id).where(
                    HypercareDefect.transition_id == transition.id,
                    HypercareDefect.status == "Open",
                )
            ).all()
        )

    ctx = rules.GateContext(
        gate=gate,
        gate_type=GATE_TYPE[gate],
        items=facts,
        open_conditions_due=open_due,
        failed_evals=failed,
        unevaluated_evals=unevaluated,
        ai_flavour=ai,
        tier_confirmed=(not ai) or (transition.tier_status == "Confirmed"),
        chain_status=chain.status if chain is not None else None,
        chain_pending_step=pending_step,
        **extra,
    )
    return GateInputs(
        ctx=ctx,
        items=by_pid,
        titles=titles,
        conditions=conditions,
        exceptions=exceptions,
        chain=chain,
        ocet_status=ocet_status,
        support_model_status=sm_status,
        unevaluated_evals=unevaluated,
        users=users,
        lens_pct=lens_pct,
    )


def person(users: dict[str, User], user_id: str | None) -> PersonRef | None:
    if not user_id:
        return None
    u = users.get(user_id)
    return PersonRef(id=user_id, name=u.name if u else user_id)


def approval_out(request: ApprovalRequest | None, users: dict[str, User]) -> GateApprovalOut | None:
    if request is None:
        return None
    return GateApprovalOut(
        request_id=request.id,
        status=request.status,
        steps=[
            ApprovalStepOut(
                step=s.step,
                role=s.role,
                label=s.label,
                approver=person(users, s.approver_user_id),
                status=s.status,
            )
            for s in request.steps
        ],
    )


def synthetic_conditions(ctx: rules.GateContext) -> list[rules.ConditionInput]:
    """Placeholder conditions for every item that would need one: used only to ask the rules whether
    the "with conditions" outcome is possible (the real dialog supplies owner / due gate / text)."""
    idx = GATE_ORDER[ctx.gate]
    if idx + 1 >= len(GATES) or ctx.gate_type == "closure":
        return []
    due = GATES[idx + 1]
    out: list[rules.ConditionInput] = []
    critical_blocks = ctx.gate_type == "decision"
    for i in ctx.items:
        if i.lens == "Compliance" or not is_open_status(i.status):
            continue
        if i.under_approved_exception or i.covered_by_condition:
            continue
        if ctx.gate == "SG3" and i.lens == "Compliance":
            continue
        if critical_blocks and i.gap_severity == ctx.critical_value:
            continue
        if GATE_ORDER.get(i.due_gate, 99) > GATE_ORDER[ctx.gate]:
            continue
        out.append(rules.ConditionInput(i.item_id, "owner", due, "condition"))
    return out


def _priority(b: rules.BlockingItem, linked: dict[str, str | None], critical_value: str) -> int:
    if b.gap_severity == critical_value:
        return 0
    if linked.get(b.item_id):
        return 1
    if b.status == "Below target":
        return 2
    return 3


def _decision_options(
    inputs: GateInputs, transition: Transition, gate: str, user: User
) -> list[DecisionOption]:
    ctx = inputs.ctx
    gate_type = GATE_TYPE[gate]
    perm = Perm.RECORD_STAGE_REVIEW if gate_type == "stage_review" else Perm.RECORD_GATE_DECISION
    synthetic = synthetic_conditions(ctx)
    options: list[DecisionOption] = []
    for outcome in GATE_OUTCOMES[gate_type]:
        reasons: list[str] = []
        if not has_perm(user.role, perm):
            reasons.append(DENIAL_REASONS[perm])
        if transition.status == "Closed":
            reasons.append("The transition is closed")
        elif gate != transition.current_gate:
            reasons.append(f"{GATE_SHORT[gate]} is not the current gate")
        if not reasons:
            conds = synthetic if outcome.endswith("with conditions") else []
            if gate_type == "stage_review":
                result = rules.validate_stage_review(ctx, outcome, conds)
            else:
                result = rules.validate_decision(ctx, outcome, conds)
            reasons.extend(result.reasons)
        options.append(DecisionOption(outcome=outcome, enabled=not reasons, reasons=reasons))
    return options


def compute_readiness_check(
    db: Session, transition: Transition, gate: str, user: User
) -> ReadinessCheckOut:
    """Build the full readiness check for ``gate`` (a valid gate code; callers validate it).

    Loads in-scope items (Applies, due <= gate, per BR-020), open conditions (covered_by_condition when
    due AFTER gate), exceptions (Approved -> under_approved_exception, Pending -> pending), eval results
    (AI flavours; failed = result present and below target, only counted as blocker at SG4_ATD),
    OCET / support-model status, the latest AtD/AtO ApprovalRequest for the gate, hypercare facts, builds
    a ``rules.gates.GateContext`` and calls ``evaluate_verdict`` / ``validate_decision`` /
    ``validate_stage_review`` (decision_options: each option re-validated with conditions=[] for the
    "Approve"/"Proceed"/"Close" variants; the "with conditions" variants are enabled when only
    Business/Technical items need conditions; Return/Hold always enabled).
    ``can_request_approval`` is True only for decision gates with verdict Ready/Ready with conditions, no
    Pending/Approved chain already open for the gate, and ``user`` holding Perm.SEND_DRAFTS; otherwise
    ``request_denied_reason`` states why. The narrative and recommended actions come from the mock AI
    service (labelled "Orion agent"); this function is READ-ONLY (no writes, no audit)."""
    inputs = load_gate_inputs(db, transition, gate)
    ctx = inputs.ctx
    users = inputs.users
    short = GATE_SHORT[gate]
    gate_type = GATE_TYPE[gate]
    result = rules.evaluate_verdict(ctx)
    facts = {i.item_id: i for i in ctx.items}

    def ref(b: rules.BlockingItem) -> GateItemRef:
        row = inputs.items.get(b.item_id)
        title = inputs.titles.get(b.item_id, "")
        owner = None
        if row is not None:
            owner = person(users, row.owner_user_id)
        else:  # failed eval metric
            title = next(
                (e.metric for e in ctx.failed_evals if e.metric_id == b.item_id), b.item_id
            )
        return GateItemRef(
            item_id=b.item_id,
            title=title,
            lens=b.lens,
            status=b.status,
            gap_severity=b.gap_severity,
            owner=owner,
            reason=b.reason,
        )

    groups = []
    for lens in LENSES:
        refs = [ref(b) for b in result.blocking if b.lens == lens]
        if refs:
            groups.append(BlockingGroup(lens=lens, items=refs))

    open_conditions = [
        OpenConditionOut(
            id=c.id,
            item_id=_item_pid(inputs, c.transition_item_id),
            text=c.text,
            due_gate=c.due_gate,
            owner=person(users, c.owner_user_id),
        )
        for c in inputs.conditions
        if c.id in ctx.open_conditions_due
    ]

    facts_c = [
        rules.ConditionFact(
            id=c.id,
            item_id=_item_pid(inputs, c.transition_item_id),
            set_at_gate=c.set_at_gate,
            due_gate=c.due_gate,
            owner_user_id=c.owner_user_id,
            text=c.text,
            status=c.status,
        )
        for c in inputs.conditions
    ]
    done = {pid: r.status in DONE_STATUSES for pid, r in inputs.items.items()}
    carried = [
        CarriedItemOut(
            item_id=c.item_id,
            title=inputs.titles.get(c.item_id, ""),
            lens=facts[c.item_id].lens if c.item_id in facts else _lens_of(inputs, c.item_id),
            status=inputs.items[c.item_id].status if c.item_id in inputs.items else "",
            condition_id=c.condition_id,
            set_at_gate=c.set_at_gate,
            due_gate=c.due_gate,
            owner=person(users, c.owner_user_id),
            text=c.text,
        )
        for c in rules.carried_items(facts_c, done, gate)
    ]

    pending_exceptions = [
        PendingExceptionOut(
            ref=e.ref, item_id=_item_pid(inputs, e.transition_item_id), status=e.status
        )
        for e in inputs.exceptions
        if e.status.startswith("Pending")
    ]

    options = _decision_options(inputs, transition, gate, user)

    # Request approval (decision gates only)
    can_request = False
    denied: str | None = None
    if gate_type != "decision":
        denied = "Only the AtD and AtO gates need an approval request"
    elif transition.status == "Closed":
        denied = "The transition is closed"
    elif gate != transition.current_gate:
        denied = f"{short} is not the current gate"
    elif inputs.chain is not None and inputs.chain.status in ("Pending", "Approved"):
        denied = f"An approval request is already {inputs.chain.status.lower()} for {short}"
    elif result.verdict == rules.VERDICT_NOT_READY:
        denied = f"Not ready for {short}: {len(result.blocking) + len(result.hard_reasons)} blocker(s) remain"
    elif not has_perm(user.role, Perm.SEND_DRAFTS):
        denied = DENIAL_REASONS[Perm.SEND_DRAFTS]
    else:
        can_request = True

    # Orion agent: actions + narrative (proposals only, BR-050)
    ordered = sorted(
        result.blocking,
        key=lambda b: _priority(
            b, {k: v.linked_module for k, v in facts.items()}, ctx.critical_value
        ),
    )
    gaps = [_gap(db, b, inputs, facts, transition, ctx) for b in ordered]
    if can_request:
        gaps.append({"ready_for_approval": True, "gate": gate, "transition_id": transition.id})
    ai = get_ai_service()
    actions = [RecommendedAction(**a) for a in ai.recommend_actions(gaps)]
    first = next((a.label for a in actions), None)
    narrative = ai.readiness_narrative(
        {
            "name": transition.name,
            "verdict": result.verdict,
            "gate_short": short,
            "blockers": [
                {"item_id": b.item_id, "title": _blocker_title(b, inputs, ctx)} for b in ordered
            ]
            + [{"item_id": "", "title": r} for r in result.hard_reasons],
            "open_conditions": [{"id": c.id, "item_id": c.item_id} for c in open_conditions],
            "first_action": first,
        }
    )

    warnings = list(result.warnings)
    return ReadinessCheckOut(
        gate=gate,
        gate_short=short,
        gate_type=gate_type,
        verdict=result.verdict,  # type: ignore[arg-type]
        verdict_label=f"{result.verdict} for {short}",
        lenses=LensValues(
            Business=inputs.lens_pct["Business"],
            Technical=inputs.lens_pct["Technical"],
            Compliance=inputs.lens_pct["Compliance"],
        ),
        blocking=groups,
        critical_gaps=[ref(b) for b in result.critical_gaps],
        open_conditions=open_conditions,
        carried_items=carried,
        pending_exceptions=pending_exceptions,
        failed_evals=[
            FailedEvalOut(
                metric_id=e.metric_id, metric=e.metric, result=e.result, target_text=e.target_text
            )
            for e in ctx.failed_evals
        ],
        unevaluated_evals=ctx.unevaluated_evals if gate == "SG4_ATD" and ctx.ai_flavour else 0,
        ocet_status=inputs.ocet_status,
        support_model_status=inputs.support_model_status,
        approval=approval_out(inputs.chain, users) if gate_type == "decision" else None,
        can_request_approval=can_request,
        request_denied_reason=denied,
        decision_options=options,
        narrative=narrative,
        narrative_by="Orion agent",
        recommended_actions=actions,
        warnings=warnings,
        generated_at=clock.now(),
    )


def _item_pid(inputs: GateInputs, item_row_id: int | None) -> str | None:
    if item_row_id is None:
        return None
    for pid, r in inputs.items.items():
        if r.id == item_row_id:
            return pid
    return None


def _lens_of(inputs: GateInputs, item_id: str) -> str:
    row = inputs.items.get(item_id)
    return row.playbook_item.lens if row is not None else ""


def _blocker_title(b: rules.BlockingItem, inputs: GateInputs, ctx: rules.GateContext) -> str:
    if b.item_id in inputs.titles:
        return inputs.titles[b.item_id]
    return next(
        (
            f"{e.metric} {e.result} vs {e.target_text}"
            for e in ctx.failed_evals
            if e.metric_id == b.item_id
        ),
        "",
    )


def _exception_approver(db: Session, inputs: GateInputs, ref: str | None) -> User | None:
    """Who a pending exception is waiting for (None when unknown)."""
    record = next((e for e in inputs.exceptions if e.ref == ref), None)
    request = db.get(ApprovalRequest, record.approval_request_id) if record else None
    if request is None or record is None or not record.status.startswith("Pending"):
        return None
    from app.domain.approvals import pending_approver  # late import (cycles)

    return pending_approver(db, request)


def _gap(
    db: Session,
    b: rules.BlockingItem,
    inputs: GateInputs,
    facts: dict[str, rules.GateItemFact],
    transition: Transition,
    ctx: rules.GateContext,
) -> dict[str, Any]:
    """Input of ``AIService.recommend_actions`` for one blocker."""
    row = inputs.items.get(b.item_id)
    if row is None:  # failed eval metric
        e = next((e for e in ctx.failed_evals if e.metric_id == b.item_id), None)
        return {
            "item_id": b.item_id,
            "title": e.metric if e else b.item_id,
            "lens": "Technical",
            "status": b.status,
            "is_eval": True,
            "metric": e.metric if e else b.item_id,
            "target_text": e.target_text if e else "",
            "transition_id": transition.id,
        }
    fact = facts.get(b.item_id)
    owner = inputs.users.get(row.owner_user_id) if row.owner_user_id else None
    exception_ref = fact.exception_ref if fact else None
    approver = _exception_approver(db, inputs, exception_ref) if exception_ref else None
    return {
        "item_id": b.item_id,
        "title": inputs.titles.get(b.item_id, ""),
        "lens": b.lens,
        "status": b.status,
        "severity": b.gap_severity,
        "owner_user_id": row.owner_user_id,
        "owner_name": owner.name if owner else None,
        "linked_module": row.linked_module,
        "transition_id": transition.id,
        "noncompliant": b.lens == "Compliance" and b.status == "Non-compliant",
        "exception_ref": exception_ref,
        "exception_approver_name": approver.name if approver else None,
        "exception_approver_role": cfg.role_short_label(db, approver.role) if approver else None,
    }
