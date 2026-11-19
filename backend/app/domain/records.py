"""Workspace records: actions, conditions, risks, hypercare defects (FR-032, FR-035, FR-036).

Domain functions never commit (the router does) and write one AuditEvent per change with actor type
``Human``: every endpoint here is a person's click (BR-050 - Orion has no write path).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.access import ensure_open, ensure_transition_role
from app.domain import audit, cfg
from app.domain.conditions import create_condition
from app.domain.ids import next_id
from app.errors import BadRequest, Conflict, NotFound
from app.models import (
    Action,
    Condition,
    HypercareDefect,
    Risk,
    Transition,
    TransitionItem,
    User,
)
from app.permissions import Perm
from app.rules.constants import ACTOR_HUMAN, DECISION_GATES, GATE_ORDER, GATE_SHORT
from app.schemas.common import PersonRef
from app.schemas.records import (
    ActionCreateIn,
    ActionOut,
    ActionPatchIn,
    ConditionCreateIn,
    ConditionOut,
    ConditionPatchIn,
    ConfirmNoDefectsIn,
    DefectCreateIn,
    DefectOut,
    DefectPatchIn,
    HypercareOut,
    RiskCreateIn,
    RiskOut,
)

ACTION_FIELDS = ("title", "item_ids", "owner_user_id", "due_date", "status", "priority", "origin")
CONDITION_FIELDS = ("owner_user_id", "due_gate", "text", "status", "close_note")
RISK_FIELDS = ("title", "rating", "decision", "item_ids")
DEFECT_FIELDS = ("title", "priority", "status", "owner_user_id")

OPEN_ACTION_STATUSES = ("Open", "In progress")


def _order(db: Session, list_key: str) -> dict[str, int]:
    """Position of each value in a dropdown list (the order the admin set), for sorting."""
    return {v: i for i, v in enumerate(cfg.option_values(db, list_key, active_only=False))}


def _default_option(db: Session, list_key: str) -> str:
    """The value used when none is given: the middle option of the list ("Medium")."""
    values = cfg.option_values(db, list_key)
    if not values:
        raise BadRequest("No options configured", [f"The list '{list_key}' has no active values"])
    return values[len(values) // 2]


# --- shared helpers -------------------------------------------------------------------------------
def get_transition(db: Session, transition_id: str) -> Transition:
    transition = db.get(Transition, transition_id)
    if transition is None:
        raise NotFound(f"Transition {transition_id} not found")
    return transition


ensure_not_closed = ensure_open  # closure freezes the record (BE#7); kept for older callers


def users_by_id(db: Session) -> dict[str, User]:
    return {u.id: u for u in db.scalars(select(User)).all()}


def person(users: dict[str, User], user_id: str | None) -> PersonRef | None:
    if not user_id:
        return None
    user = users.get(user_id)
    return PersonRef(id=user_id, name=user.name if user else user_id)


def check_owner(db: Session, owner_user_id: str | None) -> None:
    if owner_user_id is not None and db.get(User, owner_user_id) is None:
        raise BadRequest("Unknown owner", [f"User '{owner_user_id}' does not exist"])


def check_item_ids(db: Session, transition: Transition, item_ids: list[str]) -> list[str]:
    """Every id must be a TransitionItem (playbook id) of this transition; duplicates are dropped."""
    wanted = list(dict.fromkeys(item_ids))
    if not wanted:
        return []
    known = set(
        db.scalars(
            select(TransitionItem.playbook_item_id).where(
                TransitionItem.transition_id == transition.id,
                TransitionItem.playbook_item_id.in_(wanted),
            )
        ).all()
    )
    missing = [i for i in wanted if i not in known]
    if missing:
        raise BadRequest(
            "Unknown checklist items",
            [f"'{i}' is not a checklist item of {transition.id}" for i in missing],
        )
    return wanted


def find_item(db: Session, transition: Transition, playbook_item_id: str) -> TransitionItem:
    item = db.scalar(
        select(TransitionItem).where(
            TransitionItem.transition_id == transition.id,
            TransitionItem.playbook_item_id == playbook_item_id,
        )
    )
    if item is None:
        raise NotFound(f"Item {playbook_item_id} is not on {transition.id}")
    return item


def _diff(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Only the keys whose value changed (for compact before/after audit rows)."""
    keys = [k for k in after if before.get(k) != after.get(k)]
    return {k: before.get(k) for k in keys}, {k: after.get(k) for k in keys}


def _blank(value: str | None) -> bool:
    return value is not None and not value.strip()


# --- actions --------------------------------------------------------------------------------------
def action_out(action: Action, users: dict[str, User]) -> ActionOut:
    today = clock.today()
    days = (action.due_date - today).days if action.due_date else None
    return ActionOut(
        id=action.id,
        title=action.title,
        item_ids=list(action.item_ids or []),
        owner=person(users, action.owner_user_id),
        due_date=action.due_date,
        days_until_due=days,
        overdue=days is not None and days < 0 and action.status in OPEN_ACTION_STATUSES,
        status=action.status,  # type: ignore[arg-type]
        priority=action.priority,  # type: ignore[arg-type]
        origin=action.origin,
        created_by=person(users, action.created_by),
        created_at=action.created_at,
    )


def list_actions(db: Session, transition_id: str) -> list[ActionOut]:
    get_transition(db, transition_id)
    rows = db.scalars(select(Action).where(Action.transition_id == transition_id)).all()
    open_rows = sorted(
        (a for a in rows if a.status in OPEN_ACTION_STATUSES),
        key=lambda a: (a.due_date is None, a.due_date or clock.today(), a.id),
    )
    closed_rows = sorted(
        (a for a in rows if a.status not in OPEN_ACTION_STATUSES),
        key=lambda a: (a.updated_at, a.id),
        reverse=True,
    )
    users = users_by_id(db)
    return [action_out(a, users) for a in [*open_rows, *closed_rows]]


def create_action(db: Session, transition_id: str, body: ActionCreateIn, user: User) -> ActionOut:
    transition = get_transition(db, transition_id)
    ensure_transition_role(db, user, transition, Perm.MANAGE_ACTIONS)
    if _blank(body.title) or not body.title.strip():
        raise BadRequest("Invalid action", ["The action needs a title"])
    check_owner(db, body.owner_user_id)
    priority = body.priority or _default_option(db, "action_priorities")
    cfg.validate_option(db, "action_priorities", priority)
    item_ids = check_item_ids(db, transition, body.item_ids)
    action = Action(
        id=next_id(db, Action.id, "ACT-"),
        transition_id=transition.id,
        title=body.title.strip(),
        item_ids=item_ids,
        owner_user_id=body.owner_user_id,
        due_date=body.due_date,
        status="Open",
        priority=priority,
        origin="Human",
        created_by=user.id,
    )
    db.add(action)
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Action",
        entity_id=action.id,
        action="created",
        transition_id=transition.id,
        after=audit.snapshot(action, ACTION_FIELDS),
    )
    return action_out(action, users_by_id(db))


def patch_action(db: Session, action_id: str, body: ActionPatchIn, user: User) -> ActionOut:
    action = db.get(Action, action_id)
    if action is None:
        raise NotFound(f"Action {action_id} not found")
    # the OR focal, PM, Architect, OLM or IRM of the transition, or the action's owner (BE#1)
    ensure_transition_role(
        db,
        user,
        get_transition(db, action.transition_id),
        Perm.MANAGE_ACTIONS,
        also_allowed=[action.owner_user_id],
    )
    fields = body.model_fields_set
    if action.status not in OPEN_ACTION_STATUSES and not (
        "status" in fields and body.status in OPEN_ACTION_STATUSES
    ):
        raise Conflict(
            f"Action is {action.status}",
            [f"A {action.status} action can only be reopened (set status Open or In progress)"],
        )
    if "title" in fields and body.title is not None and not body.title.strip():
        raise BadRequest("Invalid action", ["The action needs a title"])
    if "owner_user_id" in fields and body.owner_user_id is not None:
        check_owner(db, body.owner_user_id)

    before = audit.snapshot(action, ACTION_FIELDS)
    if "title" in fields and body.title is not None:
        action.title = body.title.strip()
    if "owner_user_id" in fields and body.owner_user_id is not None:
        action.owner_user_id = body.owner_user_id
    if "due_date" in fields and body.due_date is not None:
        action.due_date = body.due_date
    if "status" in fields and body.status is not None:
        action.status = body.status
    if "priority" in fields and body.priority is not None:
        cfg.validate_option(db, "action_priorities", body.priority, current=action.priority)
        action.priority = body.priority
    after = audit.snapshot(action, ACTION_FIELDS)
    old, new = _diff(before, after)
    if new:
        closing = action.status not in OPEN_ACTION_STATUSES
        audit.record(
            db,
            actor=user,
            actor_type=ACTOR_HUMAN,
            entity="Action",
            entity_id=action.id,
            action="closed" if closing else "updated",
            transition_id=action.transition_id,
            before=old,
            after=new,
        )
    db.flush()
    return action_out(action, users_by_id(db))


# --- conditions -----------------------------------------------------------------------------------
def condition_out(
    condition: Condition,
    transition: Transition,
    item: TransitionItem | None,
    users: dict[str, User],
) -> ConditionOut:
    covers_now = (
        condition.status == "Open"
        and GATE_ORDER.get(condition.due_gate, -1) > GATE_ORDER[transition.current_gate]
    )
    return ConditionOut(
        id=condition.id,
        item_id=item.playbook_item_id if item else None,
        transition_item_id=condition.transition_item_id,
        item_title=item.playbook_item.title if item else None,
        set_at_gate=condition.set_at_gate,
        set_at_gate_short=GATE_SHORT.get(condition.set_at_gate, condition.set_at_gate),
        due_gate=condition.due_gate,
        due_gate_short=GATE_SHORT.get(condition.due_gate, condition.due_gate),
        owner=person(users, condition.owner_user_id),
        text=condition.text,
        status=condition.status,  # type: ignore[arg-type]
        covers_now=covers_now,
        closed_by=person(users, condition.closed_by),
        closed_at=condition.closed_at,
        close_note=condition.close_note,
    )


def _condition_item(db: Session, condition: Condition) -> TransitionItem | None:
    return (
        db.get(TransitionItem, condition.transition_item_id)
        if condition.transition_item_id is not None
        else None
    )


def list_conditions(db: Session, transition_id: str) -> list[ConditionOut]:
    transition = get_transition(db, transition_id)
    rows = db.scalars(select(Condition).where(Condition.transition_id == transition_id)).all()
    items = {
        i.id: i
        for i in db.scalars(
            select(TransitionItem).where(TransitionItem.transition_id == transition_id)
        ).all()
    }
    open_rows = sorted(
        (c for c in rows if c.status == "Open"),
        key=lambda c: (GATE_ORDER.get(c.due_gate, 99), c.id),
    )
    closed_rows = sorted(
        (c for c in rows if c.status != "Open"),
        key=lambda c: (c.closed_at or c.updated_at, c.id),
        reverse=True,
    )
    users = users_by_id(db)
    return [
        condition_out(c, transition, items.get(c.transition_item_id or -1), users)
        for c in [*open_rows, *closed_rows]
    ]


def _is_compliance(item: TransitionItem | None) -> bool:
    return item is not None and item.playbook_item.lens == "Compliance"


def create_manual_condition(
    db: Session, transition_id: str, body: ConditionCreateIn, user: User
) -> ConditionOut:
    """Add a condition by hand. The transition's OR focal or IRM may (BE#1); a condition on a
    Compliance item only the transition's assigned IRM (BE#3)."""
    transition = get_transition(db, transition_id)
    item = find_item(db, transition, body.item_id) if body.item_id else None
    ensure_transition_role(
        db,
        user,
        transition,
        Perm.MANAGE_CONDITIONS,
        roles=["IRM"] if _is_compliance(item) else None,
        phrase="manage conditions on Compliance items" if _is_compliance(item) else None,
    )
    check_owner(db, body.owner_user_id)
    condition = create_condition(
        db,
        transition=transition,
        item=item,
        set_at_gate=transition.current_gate,
        due_gate=body.due_gate,
        owner_user_id=body.owner_user_id,
        text=body.text,
        actor=user,
        actor_type=ACTOR_HUMAN,
    )
    return condition_out(condition, transition, item, users_by_id(db))


def patch_condition(
    db: Session, condition_id: str, body: ConditionPatchIn, user: User
) -> ConditionOut:
    condition = db.get(Condition, condition_id)
    if condition is None:
        raise NotFound(f"Condition {condition_id} not found")
    transition = get_transition(db, condition.transition_id)
    fields = body.model_fields_set
    # BE#3: Compliance-item conditions, and moving the due gate of a condition due at a decision
    # gate (AtD / AtO), belong to the transition's assigned IRM; the OR focal handles the rest.
    compliance = _is_compliance(_condition_item(db, condition))
    moves_decision_due = (
        "due_gate" in fields
        and body.due_gate is not None
        and body.due_gate != condition.due_gate
        and condition.due_gate in DECISION_GATES
    )
    ensure_transition_role(
        db,
        user,
        transition,
        Perm.MANAGE_CONDITIONS,
        roles=["IRM"] if compliance or moves_decision_due else None,
        phrase=(
            "manage conditions on Compliance items"
            if compliance
            else (
                "move the due gate of a condition due at a decision gate"
                if moves_decision_due
                else None
            )
        ),
    )
    if condition.status == "Closed":
        raise Conflict("Condition is already closed", ["Condition is already closed"])
    reasons: list[str] = []
    closing = "status" in fields and body.status == "Closed"
    if closing and not (body.close_note or "").strip():
        reasons.append("Closing a condition needs a close note")
    if "owner_user_id" in fields and body.owner_user_id is not None:
        check_owner(db, body.owner_user_id)
    if "due_gate" in fields and body.due_gate is not None:
        if body.due_gate not in GATE_ORDER:
            reasons.append(f"Unknown due gate '{body.due_gate}'")
        elif GATE_ORDER[body.due_gate] < GATE_ORDER.get(condition.set_at_gate, 0):
            reasons.append("A condition cannot be due before the gate it was set at")
    if "text" in fields and body.text is not None and not body.text.strip():
        reasons.append("Condition text is required")
    if reasons:
        raise BadRequest("Invalid condition", reasons)

    before = audit.snapshot(condition, CONDITION_FIELDS)
    if "owner_user_id" in fields and body.owner_user_id is not None:
        condition.owner_user_id = body.owner_user_id
    if "due_gate" in fields and body.due_gate is not None:
        condition.due_gate = body.due_gate
    if "text" in fields and body.text is not None:
        condition.text = body.text.strip()
    if closing:
        condition.status = "Closed"
        condition.close_note = (body.close_note or "").strip()
        condition.closed_by = user.id
        condition.closed_at = clock.now()
    after = audit.snapshot(condition, CONDITION_FIELDS)
    old, new = _diff(before, after)
    if new:
        audit.record(
            db,
            actor=user,
            actor_type=ACTOR_HUMAN,
            entity="Condition",
            entity_id=condition.id,
            action="closed" if closing else "updated",
            transition_id=condition.transition_id,
            before=old,
            after=new,
        )
    db.flush()
    return condition_out(condition, transition, _condition_item(db, condition), users_by_id(db))


# --- risks ----------------------------------------------------------------------------------------
def risk_out(risk: Risk) -> RiskOut:
    return RiskOut(
        id=risk.id,
        title=risk.title,
        rating=risk.rating,  # type: ignore[arg-type]
        decision=risk.decision or "",
        item_ids=list(risk.item_ids or []),
    )


def list_risks(db: Session, transition_id: str) -> list[RiskOut]:
    get_transition(db, transition_id)
    rows = db.scalars(select(Risk).where(Risk.transition_id == transition_id)).all()
    order = _order(db, "risk_ratings")
    return [risk_out(r) for r in sorted(rows, key=lambda r: (order.get(r.rating, 9), r.id))]


def create_risk(db: Session, transition_id: str, body: RiskCreateIn, user: User) -> RiskOut:
    transition = get_transition(db, transition_id)
    ensure_transition_role(db, user, transition, Perm.MANAGE_RISKS)
    if not body.title.strip():
        raise BadRequest("Invalid risk", ["The risk needs a title"])
    cfg.validate_option(db, "risk_ratings", body.rating)
    item_ids = check_item_ids(db, transition, body.item_ids)
    risk = Risk(
        id=next_id(db, Risk.id, "CR-"),
        transition_id=transition.id,
        title=body.title.strip(),
        rating=body.rating,
        decision=body.decision.strip(),
        item_ids=item_ids,
    )
    db.add(risk)
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Risk",
        entity_id=risk.id,
        action="created",
        transition_id=transition.id,
        after=audit.snapshot(risk, RISK_FIELDS),
    )
    return risk_out(risk)


# --- hypercare defects ----------------------------------------------------------------------------
def defect_out(defect: HypercareDefect, users: dict[str, User]) -> DefectOut:
    return DefectOut(
        id=defect.id,
        title=defect.title,
        priority=defect.priority,  # type: ignore[arg-type]
        status=defect.status,  # type: ignore[arg-type]
        owner=person(users, defect.owner_user_id),
    )


def hypercare(db: Session, transition: Transition) -> HypercareOut:
    rows = db.scalars(
        select(HypercareDefect).where(HypercareDefect.transition_id == transition.id)
    ).all()
    order = _order(db, "defect_priorities")
    ordered = sorted(rows, key=lambda d: (d.status != "Open", order.get(d.priority, 99), d.id))
    users = users_by_id(db)
    confirmed = bool(transition.hypercare_no_defects_confirmed)
    return HypercareOut(
        defects=[defect_out(d, users) for d in ordered],
        no_defects_confirmed=confirmed,
        tracker_in_place=bool(rows) or confirmed,
        open_p1_p2=sum(1 for d in rows if d.status == "Open" and d.priority in ("P1", "P2")),
    )


def get_hypercare(db: Session, transition_id: str) -> HypercareOut:
    return hypercare(db, get_transition(db, transition_id))


def create_defect(db: Session, transition_id: str, body: DefectCreateIn, user: User) -> DefectOut:
    transition = get_transition(db, transition_id)
    ensure_transition_role(db, user, transition, Perm.MANAGE_DEFECTS)
    if not body.title.strip():
        raise BadRequest("Invalid defect", ["The defect needs a title"])
    check_owner(db, body.owner_user_id)
    cfg.validate_option(db, "defect_priorities", body.priority)
    defect = HypercareDefect(
        id=next_id(db, HypercareDefect.id, "DEF-"),
        transition_id=transition.id,
        title=body.title.strip(),
        priority=body.priority,
        status="Open",
        owner_user_id=body.owner_user_id,
    )
    db.add(defect)
    note = ""
    if transition.hypercare_no_defects_confirmed:
        transition.hypercare_no_defects_confirmed = False
        note = "'No defects - tracker in place' confirmation reset"
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="HypercareDefect",
        entity_id=defect.id,
        action="created",
        transition_id=transition.id,
        after=audit.snapshot(defect, DEFECT_FIELDS),
        note=note,
    )
    return defect_out(defect, users_by_id(db))


def patch_defect(db: Session, defect_id: str, body: DefectPatchIn, user: User) -> DefectOut:
    defect = db.get(HypercareDefect, defect_id)
    if defect is None:
        raise NotFound(f"Defect {defect_id} not found")
    ensure_transition_role(db, user, get_transition(db, defect.transition_id), Perm.MANAGE_DEFECTS)
    fields = body.model_fields_set
    if "title" in fields and body.title is not None and not body.title.strip():
        raise BadRequest("Invalid defect", ["The defect needs a title"])
    if "owner_user_id" in fields and body.owner_user_id is not None:
        check_owner(db, body.owner_user_id)
    before = audit.snapshot(defect, DEFECT_FIELDS)
    if "title" in fields and body.title is not None:
        defect.title = body.title.strip()
    if "priority" in fields and body.priority is not None:
        cfg.validate_option(db, "defect_priorities", body.priority, current=defect.priority)
        defect.priority = body.priority
    if "status" in fields and body.status is not None:
        defect.status = body.status
    if "owner_user_id" in fields and body.owner_user_id is not None:
        defect.owner_user_id = body.owner_user_id
    after = audit.snapshot(defect, DEFECT_FIELDS)
    old, new = _diff(before, after)
    if new:
        resolved = before["status"] == "Open" and after["status"] == "Resolved"
        audit.record(
            db,
            actor=user,
            actor_type=ACTOR_HUMAN,
            entity="HypercareDefect",
            entity_id=defect.id,
            action="resolved" if resolved else "updated",
            transition_id=defect.transition_id,
            before=old,
            after=new,
        )
    db.flush()
    return defect_out(defect, users_by_id(db))


def confirm_no_defects(
    db: Session, transition_id: str, body: ConfirmNoDefectsIn, user: User
) -> HypercareOut:
    transition = get_transition(db, transition_id)
    ensure_transition_role(db, user, transition, Perm.MANAGE_DEFECTS)
    if body.confirmed:
        count = len(
            db.scalars(
                select(HypercareDefect.id).where(HypercareDefect.transition_id == transition.id)
            ).all()
        )
        if count:
            raise Conflict(
                "Resolve or remove defects first",
                [
                    "Resolve or remove defects first - 'no defects' is only valid for an empty tracker"
                ],
            )
    before = bool(transition.hypercare_no_defects_confirmed)
    transition.hypercare_no_defects_confirmed = body.confirmed
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=transition.id,
        action="hypercare_no_defects_confirmed",
        transition_id=transition.id,
        before={"hypercare_no_defects_confirmed": before},
        after={"hypercare_no_defects_confirmed": body.confirmed},
    )
    return hypercare(db, transition)
