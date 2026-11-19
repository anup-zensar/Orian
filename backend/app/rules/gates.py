"""Gate verdict, stage-review and decision rules (BR-040, spec 7.5, 7.6). PURE - no I/O, no DB.

CONTRACT ONLY (M5): the dataclasses are final, the function bodies are implemented by the M5 builder.
Callers (``domain/readiness_check.py``, ``domain/gate_actions.py``) build a :class:`GateContext` from the
database and call these functions. Item ids are PLAYBOOK item ids (``S45-014``, ``FW-008`` ...).

Vocabulary used below
---------------------
* gate ``G`` = the gate being reviewed / decided; ``o(G)`` = ``GATE_ORDER[G]``.
* "open item" = an item in scope whose status satisfies ``is_open_status`` (not done, not N/A).
  Scope = applicability ``Applies`` and ``o(due_gate) <= o(G)`` (the caller only passes such facts).
* "covered" = ``covered_by_condition`` (open condition due AFTER G, A-33) or
  ``under_approved_exception`` (A-09: an Approved exception covers the item for readiness AND for the
  gate rules). ``under_pending_exception`` does NOT cover; it is reported as a pending exception.

BR-040 points (stage reviews: SG0, SG2, SG3, SG5_HYPERCARE)
-----------------------------------------------------------
1. ``Proceed``: allowed only if no open items due <= G remain that are not covered, and (AI flavours at
   SG0) the tier is confirmed.
2. ``Proceed with conditions``: allowed when every remaining uncovered open item is Business/Technical and
   each one gets a condition in the request (owner + due gate strictly LATER than G + text); Compliance
   items must be done / N/A, under an approved exception, or already covered by a condition. Critical
   gaps are NOT a hard stop at stage reviews (only the rules above). SG0 additionally requires a
   confirmed tier for AI flavours (``ai_flavour and not tier_confirmed`` -> reason).
3. ``Hold``: always allowed (note required by the API layer).
4. SG3 rule (A-12): IRM gives no attestation at SG3 (evidence only) - Compliance-lens items are NOT
   evaluated at SG3: they never block ``Proceed`` / ``Proceed with conditions`` and need no condition.
5. Conditions supplied for items that are not open / already covered / unknown / Compliance are rejected;
   one condition per item; every uncovered open Business/Technical item must have exactly one.
6. After Proceed / Proceed with conditions the caller advances ``current_gate`` to the next gate.

Decision gates (SG4_ATD, SG6_ATO)
---------------------------------
1. The readiness check (:func:`evaluate_verdict`) uses the same computation as the decision validation.
2. Request approval is only allowed when the verdict is ``Ready`` or ``Ready with conditions``.
3. ``Approve`` / ``Approve with conditions`` require ``chain_status == "Approved"``.
4. ``Approve``: no open uncovered items due <= G, no open Critical gaps (a Critical gap is never
   coverable by a condition; only an approved exception covers it), every Compliance item due <= G is done /
   N/A / under approved exception, and at SG4_ATD no failed eval metric (7.5: a failed eval metric is a
   Technical blocker, rendered "Eval metric below target: <metric> <result> vs <target>"; metrics
   without a result are warnings only, ``unevaluated_evals``).
5. ``Approve with conditions``: as ``Approve`` except uncovered open Business/Technical items are allowed
   and each needs a condition (owner + due gate later than G + text). Compliance items can only be
   covered by an approved exception (never conditioned). Critical gaps and failed evals still block.
6. ``Return``: always allowed; the API layer requires a note; the caller cancels the chain.
7. AtO extras (SG6_ATO): no open P1/P2 defect (``open_p1_p2 == 0``); hypercare tracker in place
   (``tracker_in_place``); all AtD conditions closed (``atd_conditions_open == 0``; a re-conditioned
   one is a NEW condition and counts only if due <= G); OCET Approved (``ocet_approved``); support model
   Agreed (``support_model_agreed``). These block both Approve variants.
8. Closure: ``Close`` only if no open conditions (``open_conditions_due`` empty and
   ``atd_conditions_open == 0``), ``open_actions == 0``, ``open_defects == 0`` and all carried
   items done (no uncovered open items). No conditions allowed at closure (any supplied condition ->
   reason). ``Return`` is always allowed (note required by the API layer).
9. Carried items (:func:`carried_items`): open items from EARLIER gates that were conditioned are listed
   on every later gate page.

Verdict (:func:`evaluate_verdict`)
----------------------------------
* ``Not ready``: any hard blocker for ``Approve with conditions`` exists (critical gap not under approved
  exception, uncovered open Compliance item (not at SG3), failed eval at SG4_ATD, AtO extras unmet,
  unconfirmed tier at SG0 for AI flavours).
* ``Ready with conditions``: no hard blocker, but uncovered open Business/Technical items remain (they
  would become conditions).
* ``Ready``: nothing open and uncovered.
The approval-chain status is NOT part of the verdict (it is a separate step).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.rules.constants import GATE_ORDER, GATE_SHORT, LENSES, is_open_status

VERDICT_READY = "Ready"
VERDICT_READY_WITH_CONDITIONS = "Ready with conditions"
VERDICT_NOT_READY = "Not ready"


@dataclass(frozen=True)
class GateItemFact:
    """One in-scope item (applicability Applies, due <= gate) as seen by the gate rules."""

    item_id: str  # playbook item id, e.g. "S45-014"
    lens: str  # Business | Technical | Compliance
    due_gate: str
    status: str
    gap_severity: str | None = None
    covered_by_condition: bool = False  # open condition due AFTER the gate (A-33)
    under_approved_exception: bool = False  # A-09
    under_pending_exception: bool = False
    linked_module: str | None = None  # OCET | SUPPORT_MODEL | None
    title: str = ""
    exception_ref: str | None = None  # EX-01 (pending or approved), for display


@dataclass(frozen=True)
class FailedEval:
    metric_id: str
    metric: str
    result: str  # display text, e.g. "3.1%"
    target_text: str  # e.g. "<= 2%"


@dataclass(frozen=True)
class GateContext:
    gate: str
    gate_type: str  # stage_review | decision | closure
    items: list[GateItemFact]
    open_conditions_due: list[str] = field(
        default_factory=list
    )  # ids of open conditions due <= gate
    failed_evals: list[FailedEval] = field(default_factory=list)  # AI flavours only
    unevaluated_evals: int = 0  # warning only
    ai_flavour: bool = False
    critical_value: str = (
        "Critical"  # the gap severity that counts as critical (cfg.critical_severity)
    )
    tier_confirmed: bool = True
    chain_status: str | None = None  # None | Pending | Approved | Rejected | Cancelled
    chain_pending_step: str | None = None  # label of the Pending step, e.g. "OLM approval"
    # hypercare / AtO / closure facts
    open_p1_p2: int = 0
    tracker_in_place: bool = True
    atd_conditions_open: int = 0
    ocet_approved: bool = True
    support_model_agreed: bool = True
    open_actions: int = 0
    open_defects: int = 0


@dataclass(frozen=True)
class ConditionInput:
    """A condition requested in a review / decision body (item_id = playbook item id)."""

    item_id: str
    owner_user_id: str | None
    due_gate: str
    text: str


@dataclass(frozen=True)
class BlockingItem:
    item_id: str
    lens: str
    status: str
    gap_severity: str | None
    reason: str  # human text, e.g. "Non-compliant (Critical); exception EX-01 pending"


@dataclass(frozen=True)
class VerdictResult:
    verdict: str  # Ready | Ready with conditions | Not ready
    blocking: list[
        BlockingItem
    ]  # all open uncovered items (all lenses) + eval blockers (Technical)
    critical_gaps: list[BlockingItem]  # open Critical gaps not under an approved exception
    hard_reasons: list[str]  # non-item hard blockers (tier, AtO extras, ...) in display order
    warnings: list[str]  # unevaluated evals, pending exceptions, ...


@dataclass(frozen=True)
class RuleResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)  # shown as 409 reasons / tooltips


@dataclass(frozen=True)
class CarriedItem:
    item_id: str
    condition_id: str
    set_at_gate: str
    due_gate: str
    owner_user_id: str | None
    text: str
    item_done: bool


@dataclass(frozen=True)
class ConditionFact:
    id: str
    item_id: str | None  # playbook item id
    set_at_gate: str
    due_gate: str
    owner_user_id: str | None
    text: str
    status: str  # Open | Closed


SG3 = "SG3"
SG4_ATD = "SG4_ATD"
SG6_ATO = "SG6_ATO"
SG0 = "SG0"
_EVAL_PREFIX = "Eval metric below target"


def _short(gate: str) -> str:
    return GATE_SHORT.get(gate, gate)


def _in_scope(ctx: GateContext, item: GateItemFact) -> bool:
    """Item due by the gate; Compliance items are not evaluated at SG3 (A-12)."""
    if item.due_gate in GATE_ORDER and GATE_ORDER[item.due_gate] > GATE_ORDER[ctx.gate]:
        return False
    return not (ctx.gate == SG3 and item.lens == "Compliance")


def _covered(ctx: GateContext, item: GateItemFact) -> bool:
    """Covered for the gate rules. Conditions never cover Compliance items at decision gates;
    at closure nothing is covered by a condition."""
    if item.under_approved_exception:
        return True
    if not item.covered_by_condition:
        return False
    if ctx.gate_type == "closure":
        return False
    return not (ctx.gate_type == "decision" and item.lens == "Compliance")


def _blocking_facts(ctx: GateContext) -> list[GateItemFact]:
    """Open, in-scope, uncovered items in display order (lens, critical first, id)."""
    rows = [
        i
        for i in ctx.items
        if _in_scope(ctx, i) and is_open_status(i.status) and not _covered(ctx, i)
    ]
    return sorted(
        rows,
        key=lambda i: (
            LENSES.index(i.lens) if i.lens in LENSES else len(LENSES),
            0 if i.gap_severity == ctx.critical_value else 1,
            i.item_id,
        ),
    )


def _critical_facts(ctx: GateContext) -> list[GateItemFact]:
    """Open Critical gaps not under an approved exception (a condition never covers them)."""
    return sorted(
        (
            i
            for i in ctx.items
            if _in_scope(ctx, i)
            and is_open_status(i.status)
            and i.gap_severity == ctx.critical_value
            and not i.under_approved_exception
        ),
        key=lambda i: i.item_id,
    )


def _eval_blockers(ctx: GateContext) -> list[FailedEval]:
    if ctx.gate == SG4_ATD and ctx.ai_flavour:
        return list(ctx.failed_evals)
    return []


def _eval_reason(e: FailedEval) -> str:
    return f"{_EVAL_PREFIX}: {e.metric} {e.result} vs {e.target_text}"


def _item_reason(i: GateItemFact) -> str:
    text = i.status
    if i.gap_severity:
        text += f" ({i.gap_severity})"
    if i.under_pending_exception:
        text += (
            f"; exception {i.exception_ref} pending" if i.exception_ref else "; exception pending"
        )
    if i.linked_module == "OCET":
        text += "; OCET not approved yet"
    elif i.linked_module == "SUPPORT_MODEL":
        text += "; support model not agreed yet"
    return text


def _to_blocking(i: GateItemFact) -> BlockingItem:
    return BlockingItem(
        item_id=i.item_id,
        lens=i.lens,
        status=i.status,
        gap_severity=i.gap_severity,
        reason=_item_reason(i),
    )


def _ato_reasons(ctx: GateContext) -> list[str]:
    reasons: list[str] = []
    if ctx.open_p1_p2 > 0:
        reasons.append(f"{ctx.open_p1_p2} open P1/P2 defect(s) in hypercare")
    if not ctx.tracker_in_place:
        reasons.append("Hypercare defect tracker is not in place")
    if ctx.atd_conditions_open > 0:
        reasons.append(f"{ctx.atd_conditions_open} AtD condition(s) are still open")
    if not ctx.ocet_approved:
        reasons.append("OCET is not approved")
    if not ctx.support_model_agreed:
        reasons.append("Support model is not agreed")
    return reasons


def _closure_reasons(ctx: GateContext) -> list[str]:
    reasons: list[str] = []
    n_cond = max(len(ctx.open_conditions_due), ctx.atd_conditions_open)
    if n_cond > 0:
        reasons.append(f"{n_cond} open condition(s) must be closed before closure")
    if ctx.open_actions > 0:
        reasons.append(f"{ctx.open_actions} open action(s) must be done before closure")
    if ctx.open_defects > 0:
        reasons.append(f"{ctx.open_defects} open defect(s) must be resolved before closure")
    return reasons


def _tier_reason(ctx: GateContext) -> str | None:
    if ctx.gate == SG0 and ctx.ai_flavour and not ctx.tier_confirmed:
        return "Tier must be confirmed by IRM before SG0 can proceed"
    return None


def _hard_reasons(ctx: GateContext) -> list[str]:
    reasons: list[str] = []
    tier = _tier_reason(ctx)
    if tier:
        reasons.append(tier)
    if ctx.gate == SG6_ATO:
        reasons.extend(_ato_reasons(ctx))
    if ctx.gate_type == "closure":
        reasons.extend(_closure_reasons(ctx))
    return reasons


def evaluate_verdict(ctx: GateContext) -> VerdictResult:
    """Compute the readiness verdict and its reasons for ``ctx.gate`` (spec 8.9, BR-040 above).

    Order of ``blocking``: Business, Technical, Compliance, Critical first inside a lens, then item id.
    Failed evals (SG4_ATD, AI flavours) are appended as Technical blockers with
    ``item_id = metric_id`` and reason "Eval metric below target: <metric> <result> vs <target>".
    SG3: Compliance items are excluded entirely (A-12).
    """
    facts = _blocking_facts(ctx)
    evals = _eval_blockers(ctx)
    critical = _critical_facts(ctx)
    hard_reasons = _hard_reasons(ctx)

    blocking = [_to_blocking(i) for i in facts]
    eval_items = [
        BlockingItem(
            item_id=e.metric_id,
            lens="Technical",
            status="Below target",
            gap_severity=None,
            reason=_eval_reason(e),
        )
        for e in evals
    ]
    # Failed evals are Technical blockers: place them after the last Technical item.
    pos = 0
    for idx, b in enumerate(blocking):
        if b.lens in ("Business", "Technical"):
            pos = idx + 1
    blocking[pos:pos] = eval_items

    warnings: list[str] = []
    for i in ctx.items:
        if _in_scope(ctx, i) and i.under_pending_exception and is_open_status(i.status):
            ref = f"{i.exception_ref} " if i.exception_ref else ""
            warnings.append(f"Exception {ref}for {i.item_id} is pending approval")
    if ctx.gate == SG4_ATD and ctx.ai_flavour and ctx.unevaluated_evals > 0:
        warnings.append(f"{ctx.unevaluated_evals} eval metric(s) have no result yet")
    if ctx.gate_type == "decision" and ctx.open_conditions_due:
        warnings.append("Open condition(s) due by this gate: " + ", ".join(ctx.open_conditions_due))

    hard = bool(hard_reasons) or bool(evals)
    if ctx.gate_type in ("decision", "closure") and critical:
        hard = True
    if ctx.gate_type == "closure" and facts:
        hard = True
    if any(i.lens == "Compliance" for i in facts):
        hard = True
    if hard:
        verdict = VERDICT_NOT_READY
    elif facts:
        verdict = VERDICT_READY_WITH_CONDITIONS
    else:
        verdict = VERDICT_READY
    return VerdictResult(
        verdict=verdict,
        blocking=blocking,
        critical_gaps=[_to_blocking(i) for i in critical],
        hard_reasons=hard_reasons,
        warnings=warnings,
    )


def _ids(items: list[GateItemFact], limit: int = 6) -> str:
    ids = [i.item_id for i in items]
    text = ", ".join(ids[:limit])
    return text + (f", +{len(ids) - limit} more" if len(ids) > limit else "")


def _validate_conditions(
    ctx: GateContext, conditions: list[ConditionInput], needed: list[GateItemFact]
) -> list[str]:
    """Each needed item gets exactly one valid condition; nothing else is accepted."""
    reasons: list[str] = []
    gate_order = GATE_ORDER[ctx.gate]
    needed_ids = {i.item_id for i in needed}
    by_id = {i.item_id: i for i in ctx.items}
    seen: set[str] = set()
    for c in conditions:
        if c.item_id in seen:
            reasons.append(f"More than one condition for {c.item_id}")
            continue
        seen.add(c.item_id)
        item = by_id.get(c.item_id)
        if item is None:
            reasons.append(f"Condition for {c.item_id} rejected: unknown item")
        elif item.lens == "Compliance":
            reasons.append(
                f"Condition for {c.item_id} rejected: Compliance items cannot be conditioned"
                " (only an approved exception covers them)"
            )
        elif (
            ctx.gate_type == "decision"
            and item.gap_severity == ctx.critical_value
            and is_open_status(item.status)
        ):
            reasons.append(
                f"Condition for {c.item_id} rejected: a {ctx.critical_value} gap cannot be covered "
                "by a condition"
            )
        elif c.item_id not in needed_ids:
            reasons.append(
                f"Condition for {c.item_id} rejected: item is not open or already covered"
            )
        if not c.owner_user_id:
            reasons.append(f"Condition for {c.item_id} needs an owner")
        if not c.text or not c.text.strip():
            reasons.append(f"Condition for {c.item_id} needs a text")
        if c.due_gate not in GATE_ORDER:
            reasons.append(f"Condition for {c.item_id} has an unknown due gate '{c.due_gate}'")
        elif GATE_ORDER[c.due_gate] <= gate_order:
            reasons.append(f"Condition due gate must be after {_short(ctx.gate)}")
    missing = [i for i in needed if i.item_id not in seen]
    if missing:
        reasons.append(f"Open item(s) without a condition: {_ids(missing)}")
    return list(dict.fromkeys(reasons))


def _compliance_reasons(facts: list[GateItemFact]) -> list[str]:
    return [
        f"Compliance item {i.item_id} is open - only an approved exception can cover it"
        for i in facts
        if i.lens == "Compliance"
    ]


def _uncovered_summary(ctx: GateContext, facts: list[GateItemFact]) -> str:
    return f"{len(facts)} open item(s) due by {_short(ctx.gate)} are not covered ({_ids(facts)})"


def validate_stage_review(
    ctx: GateContext, outcome: str, conditions: list[ConditionInput]
) -> RuleResult:
    """Validate Proceed / Proceed with conditions / Hold at a stage-review gate (BR-040 stage reviews).

    Reasons are specific, e.g. "3 open items due by SG3 are not covered (FW-021, ...)", "Tier must be
    confirmed by IRM before SG0 can proceed", "Compliance item S45-014 is open - only an approved
    exception can cover it", "Condition for FW-021 needs an owner", "Condition due gate must be after SG3".
    Unknown outcome for the gate type -> not allowed.
    """
    if ctx.gate_type != "stage_review":
        return RuleResult(False, [f"{_short(ctx.gate)} is not a stage-review gate"])
    if outcome == "Hold":
        return RuleResult(True)
    if outcome not in ("Proceed", "Proceed with conditions"):
        return RuleResult(False, [f"Unknown outcome '{outcome}' for a stage review"])

    reasons: list[str] = []
    tier = _tier_reason(ctx)
    if tier:
        reasons.append(tier)
    facts = _blocking_facts(ctx)
    if outcome == "Proceed":
        if facts:
            reasons.append(_uncovered_summary(ctx, facts))
            reasons.extend(_compliance_reasons(facts))
        if conditions:
            reasons.append("Conditions can only be added with 'Proceed with conditions'")
    else:
        reasons.extend(_compliance_reasons(facts))
        needed = [i for i in facts if i.lens != "Compliance"]
        if not needed and not conditions:
            reasons.append("No open item needs a condition - use Proceed")
        reasons.extend(_validate_conditions(ctx, conditions, needed))
    return RuleResult(not reasons, list(dict.fromkeys(reasons)))


def _chain_reason(ctx: GateContext) -> str | None:
    status = ctx.chain_status
    if status == "Approved":
        return None
    if status is None:
        return "Approval has not been requested yet"
    if status == "Pending":
        step = f" ({ctx.chain_pending_step} step pending)" if ctx.chain_pending_step else ""
        return f"Approval chain is not approved yet{step}"
    return f"Approval chain was {status.lower()} - request approval again"


def validate_decision(
    ctx: GateContext, decision: str, conditions: list[ConditionInput]
) -> RuleResult:
    """Validate Approve / Approve with conditions / Return (decision gates) or Close / Return (closure).

    Encodes decision-gate points 3-8 above, including the chain-approved precondition
    ("Approval chain is not approved yet (OLM step pending)"), AtO extras and closure rules.
    """
    if ctx.gate_type == "stage_review":
        return RuleResult(False, [f"{_short(ctx.gate)} is a stage review - use the stage review"])
    if ctx.gate_type == "closure":
        allowed: tuple[str, ...] = ("Close", "Return")
    else:
        allowed = ("Approve", "Approve with conditions", "Return")
    if decision not in allowed:
        return RuleResult(False, [f"Unknown decision '{decision}' for {_short(ctx.gate)}"])
    if decision == "Return":
        return RuleResult(True)

    reasons: list[str] = []
    if ctx.gate_type == "closure":
        reasons.extend(_closure_reasons(ctx))
        facts = _blocking_facts(ctx)
        if facts:
            reasons.append(_uncovered_summary(ctx, facts))
        if conditions:
            reasons.append("Conditions are not allowed at closure")
        return RuleResult(not reasons, list(dict.fromkeys(reasons)))

    chain = _chain_reason(ctx)
    if chain:
        reasons.append(chain)
    if ctx.gate == SG6_ATO:
        reasons.extend(_ato_reasons(ctx))
    facts = _blocking_facts(ctx)
    reasons.extend(_compliance_reasons(facts))
    for i in _critical_facts(ctx):
        if i.lens != "Compliance":
            reasons.append(
                f"{ctx.critical_value} gap {i.item_id} is open - only an approved exception can "
                "cover it"
            )
    for e in _eval_blockers(ctx):
        reasons.append(_eval_reason(e))
    if decision == "Approve":
        others = [i for i in facts if i.lens != "Compliance"]
        if others:
            reasons.append(_uncovered_summary(ctx, others))
        if conditions:
            reasons.append("Conditions can only be added with 'Approve with conditions'")
    else:
        needed = [
            i for i in facts if i.lens != "Compliance" and i.gap_severity != ctx.critical_value
        ]
        if not needed and not conditions:
            reasons.append("No open item needs a condition - use Approve")
        reasons.extend(_validate_conditions(ctx, conditions, needed))
    return RuleResult(not reasons, list(dict.fromkeys(reasons)))


def carried_items(
    conditions: list[ConditionFact], item_done: dict[str, bool], gate: str
) -> list[CarriedItem]:
    """Items conditioned at an EARLIER gate than ``gate`` (``o(set_at_gate) < o(gate)``) whose condition
    is Open, or whose condition is closed but the item is not done. Ordered by due gate then item id.
    ``item_done`` maps playbook item id -> item is in a done status."""
    gate_order = GATE_ORDER[gate]
    out: list[CarriedItem] = []
    for c in conditions:
        if c.item_id is None or GATE_ORDER.get(c.set_at_gate, 99) >= gate_order:
            continue
        done = bool(item_done.get(c.item_id, False))
        if c.status != "Open" and done:
            continue
        out.append(
            CarriedItem(
                item_id=c.item_id,
                condition_id=c.id,
                set_at_gate=c.set_at_gate,
                due_gate=c.due_gate,
                owner_user_id=c.owner_user_id,
                text=c.text,
                item_done=done,
            )
        )
    return sorted(out, key=lambda x: (GATE_ORDER.get(x.due_gate, 99), x.item_id))
