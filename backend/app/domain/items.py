"""Checklist items: list with summary, PATCH with BR-030, bulk owner / N/A (FR-031, spec 7.5, 8.7 a/b).

Domain functions never commit (the router does). Every change writes ONE AuditEvent per item with the
before/after of the changed fields and actor type ``Human``; Orion has no path into this module
(BR-050). The pure rules live in ``app.rules.status``; permissions are checked here because they depend
on the item's lens.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import ensure_transition_role, transition_denial
from app.deps import ensure
from app.domain import audit, cfg
from app.domain.approvals import exception_status
from app.domain.conditions import create_condition
from app.domain.records import get_transition, person, users_by_id
from app.errors import BadRequest, Conflict, Forbidden, NotFound
from app.models import (
    Condition,
    Evidence,
    ExceptionRecord,
    Transition,
    TransitionItem,
    User,
)
from app.permissions import Perm, has_perm
from app.rules import status as status_rules
from app.rules.checklist import EXCLUDED_BY_PROJECT_TYPE, EXCLUDED_BY_TIER
from app.rules.constants import (
    ACTOR_HUMAN,
    APPLIES,
    DONE_STATUSES,
    GATE_ORDER,
    GATE_SHORT,
    LENSES,
    NA_STATUSES,
    NOT_APPLICABLE,
    NOT_STARTED,
    TO_CONFIRM,
    is_open_status,
    na_status_for,
)
from app.rules.readiness import ReadinessItem, compute_readiness
from app.schemas.items import (
    BulkItemsIn,
    BulkResultOut,
    BulkSkippedOut,
    GateLensSummaryOut,
    ItemFilters,
    ItemListOut,
    ItemOut,
    ItemPatchIn,
)

ITEM_FIELDS = (
    "status",
    "gap_severity",
    "note",
    "owner_user_id",
    "design_effectiveness",
    "applicability",
    "na_reason",
    "excluded_by",
)
APPLICABILITY_FILTER = {
    "applies": APPLIES,
    "excluded": NOT_APPLICABLE,
    "to_confirm": TO_CONFIRM,
}
LENS_ORDER = {lens: i for i, lens in enumerate(LENSES)}
_AUTO_COMPLETE = {
    "OCET": "Completes automatically when the OCET is Approved - submit the OCET for approval instead",
    "SUPPORT_MODEL": "Completes automatically when the support model is Agreed - send it for review instead",
}


def _exclusion_reason(transition: Transition, item: TransitionItem) -> str:
    if item.excluded_by == EXCLUDED_BY_TIER:
        return f"Excluded by Tier {transition.risk_tier} - change the tier (IRM) instead of overriding it"
    return (
        f"Excluded by project type {transition.project_type} - change the project type instead "
        "of overriding it"
    )


# --- context shared by list and single-item responses ---------------------------------------------
class _Context:
    """Everything needed to build ItemOut rows of one transition (a handful of queries)."""

    def __init__(self, db: Session, transition: Transition) -> None:
        self.db = db
        self._edit_cache: dict[tuple[str, bool], tuple[bool, str | None]] = {}
        self.users = users_by_id(db)
        self.evidence_count: dict[int, int] = dict(
            db.execute(
                select(Evidence.transition_item_id, func.count())
                .where(
                    Evidence.transition_id == transition.id,
                    Evidence.transition_item_id.is_not(None),
                )
                .group_by(Evidence.transition_item_id)
            ).all()
        )
        self.open_condition: dict[int, tuple[int, str]] = {}  # item -> (due order, condition id)
        for cond in db.scalars(
            select(Condition)
            .where(
                Condition.transition_id == transition.id,
                Condition.status == "Open",
                Condition.transition_item_id.is_not(None),
            )
            .order_by(Condition.id)
        ).all():
            order = GATE_ORDER.get(cond.due_gate, -1)
            current = self.open_condition.get(cond.transition_item_id)  # type: ignore[arg-type]
            if current is None or order > current[0]:
                self.open_condition[cond.transition_item_id] = (order, cond.id)  # type: ignore[index]
        self.exceptions: dict[int, ExceptionRecord] = {}  # latest (highest ref) per item
        self.approved_exception: set[int] = set()
        for exc in db.scalars(
            select(ExceptionRecord)
            .where(
                ExceptionRecord.transition_id == transition.id,
                ExceptionRecord.transition_item_id.is_not(None),
            )
            .order_by(ExceptionRecord.ref)
        ).all():
            self.exceptions[exc.transition_item_id] = exc  # type: ignore[index]
            if exc.status == "Approved":
                self.approved_exception.add(exc.transition_item_id)  # type: ignore[arg-type]

    def covered(self, item: TransitionItem, gate_order: int) -> bool:
        """Open condition due after the gate, or an approved exception (BR-020, A-09, A-33)."""
        cond = self.open_condition.get(item.id)
        return (cond is not None and cond[0] > gate_order) or item.id in self.approved_exception


def _status_perm(lens: str) -> Perm:
    return Perm.UPDATE_C_STATUS if lens == "Compliance" else Perm.UPDATE_BT_STATUS


def _also_allowed(item: TransitionItem, lens: str) -> list[str | None]:
    """The item owner may update a Business/Technical item (when their role holds the permission)."""
    return [] if lens == "Compliance" else [item.owner_user_id]


def _edit_state(
    ctx: _Context, transition: Transition, user: User, item: TransitionItem, lens: str
) -> tuple[bool, str | None]:
    """(can_edit, reason) of the status control for this user, transition and item (BE#1)."""
    key = (lens, user.id == item.owner_user_id and lens != "Compliance")
    if key not in ctx._edit_cache:
        reason = transition_denial(
            ctx.db,
            user,
            transition,
            _status_perm(lens),
            also_allowed=_also_allowed(item, lens),
        )
        if reason is None and transition.status == "Closed":
            reason = "The transition is closed"
        ctx._edit_cache[key] = (reason is None, reason)
    return ctx._edit_cache[key]


def _item_out(
    item: TransitionItem,
    transition: Transition,
    ctx: _Context,
    user: User,
    gate_order: int,
) -> ItemOut:
    pb = item.playbook_item
    can_edit, reason = _edit_state(ctx, transition, user, item, pb.lens)
    cond = ctx.open_condition.get(item.id)
    exc = ctx.exceptions.get(item.id)
    return ItemOut(
        id=item.id,
        item_id=item.playbook_item_id,
        title=pb.title,
        description=pb.description,
        detail=pb.detail,
        source=pb.source,  # type: ignore[arg-type]
        source_label=pb.source_label,
        source_sheet=pb.source_sheet,
        source_cell=pb.source_cell,
        category=pb.category,
        kind=pb.kind,
        gate=item.due_gate,
        gate_short=GATE_SHORT.get(item.due_gate, item.due_gate),
        lens=pb.lens,  # type: ignore[arg-type]
        lens_is_suggested=pb.lens_is_suggested,
        tier_label=pb.tier_label,
        tier_to_confirm=pb.tier_unspecified,
        applicability=item.applicability,  # type: ignore[arg-type]
        excluded_by=item.excluded_by,
        na_reason=item.na_reason,
        status=item.status,
        allowed_statuses=list(status_rules.allowed_statuses(pb.lens)),
        gap_severity=item.gap_severity,  # type: ignore[arg-type]
        design_effectiveness=(
            item.design_effectiveness if pb.lens == "Compliance" else None
        ),  # type: ignore[arg-type]
        note=item.note or "",
        owner=person(ctx.users, item.owner_user_id),
        linked_module=item.linked_module,
        evidence_count=ctx.evidence_count.get(item.id, 0),
        open_condition_id=cond[1] if cond else None,
        exception_ref=exc.ref if exc else None,
        exception_status=exception_status(ctx.db, exc) if exc else None,
        covered=is_open_status(item.status) and ctx.covered(item, gate_order),
        last_updated_by=person(ctx.users, item.last_updated_by),
        last_updated_source=item.last_updated_source,
        updated_at=item.updated_at,
        can_edit=can_edit,
        edit_denied_reason=reason,
    )


def _sort_key(item: TransitionItem) -> tuple[int, int, int, int]:
    pb = item.playbook_item
    return (
        GATE_ORDER.get(item.due_gate, 99),
        LENS_ORDER.get(pb.lens, 9),
        pb.sort_order,
        item.id,
    )


def _transition_items(db: Session, transition_id: str) -> list[TransitionItem]:
    return list(
        db.scalars(
            select(TransitionItem).where(TransitionItem.transition_id == transition_id)
        ).all()
    )


# --- list -----------------------------------------------------------------------------------------
def _summary(items: list[TransitionItem], ctx: _Context, gate: str) -> list[GateLensSummaryOut]:
    gate_order = GATE_ORDER[gate]
    readiness = compute_readiness(
        [
            ReadinessItem(
                lens=i.playbook_item.lens,
                due_gate=i.due_gate,
                applicability=i.applicability,
                status=i.status,
                gap_severity=i.gap_severity,
                covered=ctx.covered(i, gate_order),
            )
            for i in items
        ],
        gate,
    )
    return [
        GateLensSummaryOut(
            lens=lens,  # type: ignore[arg-type]
            scope=readiness.lenses[lens].scope,
            done=readiness.lenses[lens].done,
            in_progress=readiness.lenses[lens].in_progress,
            not_started=readiness.lenses[lens].not_started,
            open_gaps=readiness.lenses[lens].open_gaps,
            critical_gaps=readiness.lenses[lens].critical_gaps,
            readiness_pct=readiness.lenses[lens].readiness_pct,
        )
        for lens in LENSES
    ]


def list_items(db: Session, transition_id: str, filters: ItemFilters, user: User) -> ItemListOut:
    transition = get_transition(db, transition_id)
    gate = filters.gate or transition.current_gate
    if gate not in GATE_ORDER:
        raise BadRequest("Unknown gate", [f"'{gate}' is not a gate code ({', '.join(GATE_ORDER)})"])
    gate_order = GATE_ORDER[gate]

    items = _transition_items(db, transition.id) if transition.assessment_launched_at else []
    ctx = _Context(db, transition)
    excluded = [i for i in items if i.applicability == NOT_APPLICABLE]

    selected = items
    if not filters.all_gates:
        selected = [i for i in selected if GATE_ORDER.get(i.due_gate, 99) <= gate_order]
    if filters.applicability != "all":
        wanted = APPLICABILITY_FILTER[filters.applicability]
        selected = [i for i in selected if i.applicability == wanted]
    if filters.lens:
        selected = [i for i in selected if i.playbook_item.lens == filters.lens]
    if filters.source:
        selected = [i for i in selected if i.playbook_item.source == filters.source]
    if filters.status:
        selected = [i for i in selected if i.status == filters.status]
    if filters.owner:
        selected = [i for i in selected if i.owner_user_id == filters.owner]
    if filters.mine:
        selected = [i for i in selected if i.owner_user_id == user.id]
    if filters.q and filters.q.strip():
        needle = filters.q.strip().lower()

        def matches(i: TransitionItem) -> bool:
            owner = ctx.users.get(i.owner_user_id or "")
            haystack = (
                i.playbook_item_id,
                i.playbook_item.title,
                i.playbook_item.description,
                owner.name if owner else "",
            )
            return any(needle in (h or "").lower() for h in haystack)

        selected = [i for i in selected if matches(i)]

    selected.sort(key=_sort_key)
    return ItemListOut(
        gate=gate,
        items=[_item_out(i, transition, ctx, user, gate_order) for i in selected],
        summary=_summary(items, ctx, gate),
        excluded_count=len(excluded),
        excluded_by_tier_count=sum(1 for i in excluded if i.excluded_by == "tier"),
    )


# --- PATCH ----------------------------------------------------------------------------------------
def _check_patch_permissions(
    db: Session,
    user: User,
    transition: Transition,
    item: TransitionItem,
    lens: str,
    body: ItemPatchIn,
) -> None:
    """Dynamic permissions by lens AND assignment on the item's transition (BE#1, spec 3.3).

    Business/Technical status, note and owner: the transition's OR focal / PM / Architect / OLM, or the
    item's owner. Compliance status / severity / design effectiveness: the transition's IRM (the owner
    may still edit note and owner). Applicability and N/A: the OR focal (B/T) or IRM (Compliance).
    """
    fields = body.model_fields_set
    compliance = lens == "Compliance"
    status_perm = _status_perm(lens)
    scope_perm = Perm.UPDATE_C_STATUS if compliance else Perm.CONFIRM_SCOPE
    owner_ok = _also_allowed(item, lens)

    if "status" in fields and body.status is not None and body.status != item.status:
        ensure_transition_role(db, user, transition, status_perm, also_allowed=owner_ok)
        if body.status in NA_STATUSES:
            ensure_transition_role(db, user, transition, scope_perm)
    if "gap_severity" in fields and body.gap_severity is not None:
        ensure_transition_role(db, user, transition, status_perm, also_allowed=owner_ok)
    if "design_effectiveness" in fields and body.design_effectiveness is not None:
        ensure_transition_role(db, user, transition, Perm.UPDATE_C_STATUS)
    if body.applicability is not None and body.applicability != item.applicability:
        ensure_transition_role(db, user, transition, scope_perm)
    if "na_reason" in fields and body.na_reason is not None:
        ensure_transition_role(db, user, transition, scope_perm)
    if ("note" in fields and body.note is not None) or (
        "owner_user_id" in fields and body.owner_user_id is not None
    ):
        if compliance:
            if user.id != item.owner_user_id:
                ensure_transition_role(db, user, transition, Perm.UPDATE_C_STATUS)
        else:
            ensure_transition_role(
                db, user, transition, Perm.UPDATE_BT_STATUS, also_allowed=owner_ok
            )


def _on_offer(db: Session, list_key: str, current: str | None) -> list[str]:
    """Active values of a dropdown list, plus the value already on the item (it may have been retired
    since, and stays valid while unchanged)."""
    values = cfg.option_values(db, list_key)
    return [*values, current] if current and current not in values else values


def _input_errors(db: Session, lens: str, body: ItemPatchIn, item: TransitionItem) -> list[str]:
    fields = body.model_fields_set
    reasons = status_rules.input_errors(
        severities=_on_offer(db, "severities", item.gap_severity),
        design_options=_on_offer(db, "design_effectiveness", item.design_effectiveness),
        lens=lens,
        status=body.status if "status" in fields else None,
        gap_severity=body.gap_severity if "gap_severity" in fields else None,
        design_effectiveness=(
            body.design_effectiveness if "design_effectiveness" in fields else None
        ),
    )
    if (
        lens != "Compliance"
        and "design_effectiveness" in fields
        and body.design_effectiveness is not None
    ):
        reasons.append("Design effectiveness applies to Compliance items only")
    if body.owner_user_id is not None and db.get(User, body.owner_user_id) is None:
        reasons.append(f"User '{body.owner_user_id}' does not exist")
    if body.condition is not None:
        cond = body.condition
        if db.get(User, cond.owner_user_id) is None:
            reasons.append(f"Condition owner '{cond.owner_user_id}' does not exist")
        if cond.due_gate not in GATE_ORDER:
            reasons.append(f"Unknown due gate '{cond.due_gate}'")
    return reasons


def patch_item(db: Session, item_id: int, body: ItemPatchIn, user: User) -> ItemOut:
    item = db.get(TransitionItem, item_id)
    if item is None:
        raise NotFound(f"Item {item_id} not found")
    transition = db.get(Transition, item.transition_id)
    if transition is None:
        raise NotFound(f"Transition {item.transition_id} not found")
    lens = item.playbook_item.lens
    fields = body.model_fields_set

    _check_patch_permissions(db, user, transition, item, lens, body)
    reasons = _input_errors(db, lens, body, item)
    if reasons:
        raise BadRequest("Invalid item update", reasons)
    if transition.status == "Closed":
        raise Conflict("Transition is closed", [f"{transition.id} is closed - items are read-only"])
    if transition.assessment_launched_at is None:
        raise Conflict(
            "Assessment not launched", ["Launch the assessment before updating checklist items"]
        )

    before = audit.snapshot(item, ITEM_FIELDS)

    # --- resulting state -------------------------------------------------------------------------
    new_status = item.status
    new_app = item.applicability
    new_na_reason = item.na_reason
    new_excluded_by = item.excluded_by
    violations: list[str] = []
    status_given = "status" in fields and body.status is not None
    app_given = "applicability" in fields and body.applicability is not None
    status_changes = status_given and body.status != item.status
    app_changes = app_given and body.applicability != item.applicability

    # BE#4: items fed by the OCET / support model complete automatically with the approval.
    if status_changes and body.status in DONE_STATUSES and item.linked_module in _AUTO_COMPLETE:
        raise Conflict("Completes automatically", [_AUTO_COMPLETE[item.linked_module]])
    # BE#10: an item the tier / project type excluded is only re-included by changing the tier.
    if (
        app_changes
        and body.applicability != NOT_APPLICABLE
        and item.excluded_by in (EXCLUDED_BY_TIER, EXCLUDED_BY_PROJECT_TYPE)
    ):
        raise Conflict(
            "Excluded by the tier" if item.excluded_by == EXCLUDED_BY_TIER else "Excluded by type",
            [_exclusion_reason(transition, item)],
        )

    if status_given:
        new_status = body.status  # type: ignore[assignment]
    if "na_reason" in fields and body.na_reason is not None:
        new_na_reason = body.na_reason.strip() or None

    if app_given:
        new_app = body.applicability  # type: ignore[assignment]
        if new_app == NOT_APPLICABLE:
            if status_given and body.status not in NA_STATUSES:
                violations.append(
                    "Applicability 'Not applicable' conflicts with a non-N/A status in the same request"
                )
            new_status = na_status_for(lens)
        elif item.status in NA_STATUSES and not (status_given and body.status not in NA_STATUSES):
            new_status = NOT_STARTED
    elif status_given and body.status in NA_STATUSES:
        new_app = NOT_APPLICABLE
    elif status_given and item.applicability == NOT_APPLICABLE:
        violations.append(
            "The item is not applicable - restore its applicability (Applies) before changing its status"
        )

    if new_app == NOT_APPLICABLE and (app_changes or status_changes):
        new_excluded_by = None  # a human's own N/A (A-40)
    if new_app != NOT_APPLICABLE and item.applicability == NOT_APPLICABLE:
        new_excluded_by = None
    if new_status not in NA_STATUSES and new_app != NOT_APPLICABLE:
        new_na_reason = None

    new_note = (body.note or "") if "note" in fields and body.note is not None else item.note or ""
    new_severity = (
        body.gap_severity
        if "gap_severity" in fields and body.gap_severity is not None
        else item.gap_severity
    )
    if status_rules.clears_gap_severity(new_status):
        new_severity = None
    new_de = (
        body.design_effectiveness
        if "design_effectiveness" in fields and body.design_effectiveness is not None
        else item.design_effectiveness
    )

    # --- BR-030 -------------------------------------------------------------------------------
    touched_gap = status_changes or "gap_severity" in fields or "note" in fields
    touched_design = status_changes or "design_effectiveness" in fields
    touched_na = (
        status_changes or app_changes or "na_reason" in fields
    ) and new_status in NA_STATUSES
    entering_conditions = status_changes and new_status == status_rules.COMPLIANT_WITH_CONDITIONS
    cond_in = body.condition
    if entering_conditions:
        if cond_in is None:
            violations.append(
                "'Compliant with conditions' needs a condition (owner, due gate and text)"
            )
        else:
            violations.extend(
                status_rules.missing_condition_fields(
                    cond_in.owner_user_id, cond_in.due_gate, cond_in.text
                )
            )
            if (
                cond_in.due_gate in GATE_ORDER
                and GATE_ORDER[cond_in.due_gate] < GATE_ORDER[transition.current_gate]
            ):
                violations.append("The condition cannot be due before the current gate")
    violations.extend(
        status_rules.rule_violations(
            lens=lens,
            status=new_status,
            gap_severity=new_severity,
            note=new_note,
            design_effectiveness=new_de,
            na_reason=new_na_reason,
            has_condition=True,  # checked above with the exact reasons
            check_gap=touched_gap,
            check_design=touched_design and new_status == status_rules.COMPLIANT,
            check_na=touched_na,
            check_condition=False,
            severities=cfg.option_values(db, "severities"),
        )
    )
    if violations:
        raise Conflict("Status rule violated", list(dict.fromkeys(violations)))

    # --- apply --------------------------------------------------------------------------------
    item.status = new_status
    item.applicability = new_app
    item.na_reason = new_na_reason
    item.excluded_by = new_excluded_by
    item.gap_severity = new_severity
    item.note = new_note
    if lens == "Compliance":
        item.design_effectiveness = new_de
    if "owner_user_id" in fields and body.owner_user_id is not None:
        item.owner_user_id = body.owner_user_id

    after = audit.snapshot(item, ITEM_FIELDS)
    changed = [k for k in ITEM_FIELDS if before.get(k) != after.get(k)]
    condition: Condition | None = None
    if entering_conditions and cond_in is not None:
        condition = create_condition(
            db,
            transition=transition,
            item=item,
            set_at_gate=transition.current_gate,
            due_gate=cond_in.due_gate,
            owner_user_id=cond_in.owner_user_id,
            text=cond_in.text,
            actor=user,
            actor_type=ACTOR_HUMAN,
        )
    if changed:
        item.last_updated_by = user.id
        item.last_updated_source = "Human"
        db.flush()
        audit.record(
            db,
            actor=user,
            actor_type=ACTOR_HUMAN,
            entity="TransitionItem",
            entity_id=item.id,
            action="updated",
            transition_id=transition.id,
            before={k: before[k] for k in changed},
            after={k: after[k] for k in changed},
            note=(
                f"{item.playbook_item_id}"
                + (f" - condition {condition.id} created" if condition else "")
            ),
        )
    db.flush()
    ctx = _Context(db, transition)
    return _item_out(item, transition, ctx, user, GATE_ORDER[transition.current_gate])


# --- bulk -----------------------------------------------------------------------------------------
def bulk_items(db: Session, body: BulkItemsIn, user: User) -> BulkResultOut:
    if not has_perm(user.role, Perm.CONFIRM_SCOPE):
        if body.owner_user_id is not None and body.mark_na is None:
            raise Forbidden("Only the OR focal can change items in bulk")  # owner-only request
        ensure(user, Perm.CONFIRM_SCOPE)
    reasons: list[str] = []
    if body.owner_user_id is None and body.mark_na is None:
        reasons.append("Choose an owner and/or mark the items N/A")
    if body.mark_na is not None and not body.mark_na.reason.strip():
        reasons.append("Marking items N/A needs a reason")
    if body.owner_user_id is not None and db.get(User, body.owner_user_id) is None:
        reasons.append(f"User '{body.owner_user_id}' does not exist")
    if reasons:
        raise BadRequest("Invalid bulk request", reasons)

    updated: list[int] = []
    skipped: list[BulkSkippedOut] = []
    transitions: dict[str, Transition | None] = {}
    for item_id in dict.fromkeys(body.item_ids):
        item = db.get(TransitionItem, item_id)
        if item is None:
            skipped.append(BulkSkippedOut(id=item_id, reason="Item not found"))
            continue
        if item.transition_id not in transitions:
            transitions[item.transition_id] = db.get(Transition, item.transition_id)
        transition = transitions[item.transition_id]
        denial = (
            transition_denial(
                db, user, transition, Perm.CONFIRM_SCOPE, phrase="change its items in bulk"
            )
            if transition is not None
            else "Transition not found"
        )
        if transition is None or denial is not None:
            skipped.append(BulkSkippedOut(id=item_id, reason=denial or "Transition not found"))
            continue
        if transition.status == "Closed":
            skipped.append(BulkSkippedOut(id=item_id, reason="The transition is closed"))
            continue
        lens = item.playbook_item.lens
        do_na = body.mark_na is not None
        if do_na and lens == "Compliance":
            skipped.append(
                BulkSkippedOut(
                    id=item_id, reason="Only IRM can mark Compliance items not applicable"
                )
            )
            continue
        if do_na and item.status in NA_STATUSES and body.owner_user_id is None:
            skipped.append(BulkSkippedOut(id=item_id, reason="Item is already N/A"))
            continue

        before = audit.snapshot(item, ITEM_FIELDS)
        if body.owner_user_id is not None:
            item.owner_user_id = body.owner_user_id
        if do_na and item.status not in NA_STATUSES and body.mark_na is not None:
            item.applicability = NOT_APPLICABLE
            item.status = na_status_for(lens)
            item.na_reason = body.mark_na.reason.strip()
            item.excluded_by = None
            item.gap_severity = None
        after = audit.snapshot(item, ITEM_FIELDS)
        changed = [k for k in ITEM_FIELDS if before.get(k) != after.get(k)]
        if not changed:
            skipped.append(BulkSkippedOut(id=item_id, reason="Nothing to change"))
            continue
        item.last_updated_by = user.id
        item.last_updated_source = "Human"
        db.flush()
        audit.record(
            db,
            actor=user,
            actor_type=ACTOR_HUMAN,
            entity="TransitionItem",
            entity_id=item.id,
            action="updated",
            transition_id=item.transition_id,
            before={k: before[k] for k in changed},
            after={k: after[k] for k in changed},
            note=f"{item.playbook_item_id} - bulk update",
        )
        updated.append(item_id)
    db.flush()
    return BulkResultOut(updated=updated, skipped=skipped)
