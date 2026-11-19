"""Per-transition access control (review finding BE#1; spec 3.1 "the OR focal owns transitions", 3.3).

Rule: a transition-scoped permission = the user's ROLE holds the permission (spec 3.3 matrix in
``app.permissions``) AND the user is the person assigned to that role on THIS transition
(``Transition.or_focal_user_id``, ``pm_user_id``, ``architect_user_id``, ``olm_user_id``, ``irm_user_id``).
Roles without a slot on a transition (Planner, Leadership, Admin) never pass a transition-scoped check:
the Planner acts through approval steps, Leadership is read-only and the Admin configures (and may
re-assign people on a transition through ``ensure_admin_or_assigned``).

Where to call it: at the top of every domain function that a HUMAN invokes to change a transition's data,
so an Orion proposal accepted by a human inherits the same check (BR-050). System paths - seed loader,
demo fast-forward, approval completion hooks, the reminder engine and autonomous sends - never call it.

Only this module knows how roles map to transition slots (``assigned_user_id``).

CR-01: the five slots are fixed (``TRANSITION_ROLE_COLUMN``); the role labels shown in messages come
from ``app.domain.cfg`` so an Admin can rename them. The Admin has no workflow override: ADMIN never
has a slot, so granting a transition-scoped permission to ADMIN has no effect on transitions.
"""

from __future__ import annotations

from collections.abc import Collection

from sqlalchemy.orm import Session

from app.domain import cfg
from app.errors import Conflict, Forbidden, NotFound
from app.models import Transition, User
from app.permissions import DENIAL_REASONS, Perm, has_perm

# Role -> the Transition column holding the person assigned to that role (order = message order).
TRANSITION_ROLE_COLUMN: dict[str, str] = {
    "OR_FOCAL": "or_focal_user_id",
    "PM": "pm_user_id",
    "ARCHITECT": "architect_user_id",
    "OLM": "olm_user_id",
    "IRM": "irm_user_id",
}

# Verb phrase per permission for "Only <who> can <phrase>" messages.
PERM_PHRASE: dict[Perm, str] = {
    Perm.EDIT_TRANSITION: "edit this transition",
    Perm.PROPOSE_TIER: "propose the tier",
    Perm.CONFIRM_TIER: "confirm the tier",
    Perm.CONFIRM_SCOPE: "confirm scope and applicability",
    Perm.UPDATE_BT_STATUS: "update Business/Technical items",
    Perm.UPDATE_C_STATUS: "set compliance status",
    Perm.MANAGE_EVIDENCE: "upload or link evidence",
    Perm.REVIEW_EVIDENCE_BT: "accept or reject Business/Technical evidence",
    Perm.REVIEW_EVIDENCE_C: "accept or reject Compliance evidence",
    Perm.MANAGE_ACTIONS: "create or change actions",
    Perm.RECORD_STAGE_REVIEW: "record stage reviews",
    Perm.RECORD_GATE_DECISION: "record gate decisions",
    Perm.EDIT_OCET: "edit the OCET",
    Perm.EDIT_SUPPORT_MODEL: "edit the support model",
    Perm.SEND_DRAFTS: "send Orion drafts",
    Perm.MANAGE_CONDITIONS: "manage conditions",
    Perm.REQUEST_EXCEPTION: "request an exception",
    Perm.MANAGE_RISKS: "manage risks",
    Perm.MANAGE_DEFECTS: "manage hypercare defects",
    Perm.EDIT_EVAL_RESULTS: "enter eval results",
    Perm.EDIT_AI_PROFILE: "edit the AI profile",
    Perm.TOGGLE_AUTONOMOUS: "change autonomous mode",
    Perm.RUN_REMINDERS: "run the reminder engine",
}


def assigned_user_id(transition: Transition, role: str) -> str | None:
    """The id of the person holding ``role`` on ``transition`` (None for roles without a slot or an
    empty slot)."""
    column = TRANSITION_ROLE_COLUMN.get(role)
    return (getattr(transition, column) or None) if column else None


def is_assigned(user: User, transition: Transition) -> bool:
    """True when ``user`` is the person assigned to their own role on ``transition``."""
    return assigned_user_id(transition, user.role) == user.id


def _name(db: Session, user_id: str) -> str:
    person = db.get(User, user_id)
    return person.name if person is not None else user_id


def transition_denial(
    db: Session,
    user: User,
    transition: Transition,
    perm: Perm,
    *,
    also_allowed: Collection[str | None] = (),
    roles: Collection[str] | None = None,
    phrase: str | None = None,
) -> str | None:
    """None when ``user`` may use ``perm`` on ``transition``, else the human reason (tooltip / 403 text).

    * The role must hold ``perm`` (else the spec 3.3 reason, e.g. "Only IRM can set compliance status").
    * ``roles`` narrows the roles that qualify (e.g. ``["IRM"]`` for conditions on Compliance items).
    * ``also_allowed`` lists extra user ids that pass when their role qualifies (e.g. the item owner).
    * Otherwise the user must be the person assigned to their role on this transition.
    """
    if not has_perm(user.role, perm):
        return DENIAL_REASONS[perm]
    qualifying = [
        role
        for role in TRANSITION_ROLE_COLUMN
        if has_perm(role, perm) and (roles is None or role in roles)
    ]
    if user.role in qualifying and (
        user.id in also_allowed or assigned_user_id(transition, user.role) == user.id
    ):
        return None
    what = phrase or PERM_PHRASE.get(perm, "do this")
    filled = [(role, assigned_user_id(transition, role)) for role in qualifying]
    filled = [(role, uid) for role, uid in filled if uid]
    if not filled:
        labels = " or ".join(cfg.role_phrase_label(db, role) for role in qualifying) or "person"
        return f"{transition.id} has no {labels} assigned - ask an Admin to assign one"
    if len(filled) == 1:
        role, uid = filled[0]
        reason = (
            f"Only {_name(db, uid)}, the {cfg.role_phrase_label(db, role)} of {transition.id}, "
            f"can {what}"
        )
    else:
        people = ", ".join(
            f"{_name(db, uid)} ({cfg.role_phrase_label(db, role)})" for role, uid in filled
        )
        reason = f"Only the people assigned to {transition.id} ({people}) can {what}"
    if user.role in qualifying and assigned_user_id(transition, user.role) is None:
        reason += (
            f". {transition.id} has no {cfg.role_phrase_label(db, user.role)} assigned"
            " - ask an Admin to assign one"
        )
    return reason


def ensure_open(transition: Transition) -> None:
    """409 when the transition is Closed (closure freezes the record, BE#7)."""
    if transition.status == "Closed":
        raise Conflict(
            "Transition is closed",
            [f"{transition.id} is closed - records can no longer be added or changed"],
        )


def ensure_transition_role(
    db: Session,
    user: User,
    transition: Transition,
    perm: Perm,
    *,
    also_allowed: Collection[str | None] = (),
    roles: Collection[str] | None = None,
    phrase: str | None = None,
    allow_closed: bool = False,
) -> None:
    """403 with the reason from ``transition_denial``; then 409 if the transition is Closed
    (unless ``allow_closed``). Permission is evaluated before the closed check."""
    reason = transition_denial(
        db, user, transition, perm, also_allowed=also_allowed, roles=roles, phrase=phrase
    )
    if reason is not None:
        raise Forbidden(reason)
    if not allow_closed:
        ensure_open(transition)


def ensure_admin(user: User, phrase: str) -> None:
    """403 "Only an Admin can <phrase>" unless the user is an Admin."""
    if user.role != "ADMIN":
        raise Forbidden(f"Only an Admin can {phrase}")


def ensure_admin_or_assigned(
    db: Session,
    user: User,
    transition: Transition,
    perm: Perm,
    *,
    phrase: str | None = None,
    allow_closed: bool = False,
) -> None:
    """An Admin passes (the closed check still applies); anyone else needs ``ensure_transition_role``."""
    if user.role == "ADMIN":
        if not allow_closed:
            ensure_open(transition)
        return
    ensure_transition_role(db, user, transition, perm, phrase=phrase, allow_closed=allow_closed)


def transition_for(db: Session, transition_id: str) -> Transition:
    """Load a transition or raise 404."""
    transition = db.get(Transition, transition_id)
    if transition is None:
        raise NotFound(f"Transition {transition_id} not found")
    return transition


# Permissions checked per transition (exposed to the UI as TransitionDetailOut.access).
TRANSITION_PERMS: tuple[Perm, ...] = (
    Perm.EDIT_TRANSITION,
    Perm.PROPOSE_TIER,
    Perm.CONFIRM_TIER,
    Perm.CONFIRM_SCOPE,
    Perm.UPDATE_BT_STATUS,
    Perm.UPDATE_C_STATUS,
    Perm.MANAGE_EVIDENCE,
    Perm.REVIEW_EVIDENCE_BT,
    Perm.REVIEW_EVIDENCE_C,
    Perm.MANAGE_ACTIONS,
    Perm.RECORD_STAGE_REVIEW,
    Perm.RECORD_GATE_DECISION,
    Perm.EDIT_OCET,
    Perm.EDIT_SUPPORT_MODEL,
    Perm.SEND_DRAFTS,
    Perm.MANAGE_CONDITIONS,
    Perm.REQUEST_EXCEPTION,
    Perm.MANAGE_RISKS,
    Perm.MANAGE_DEFECTS,
    Perm.EDIT_EVAL_RESULTS,
    Perm.EDIT_AI_PROFILE,
    Perm.TOGGLE_AUTONOMOUS,
)


def access_map(db: Session, user: User, transition: Transition) -> dict[str, str | None]:
    """Permission code -> None (allowed) or the reason (tooltip) for every transition-scoped
    permission of ``user`` on ``transition``. A Closed transition denies every write with the
    closed reason. ``edit_transition`` also passes for an Admin (re-assignment, BE#2)."""
    closed_reason = (
        f"{transition.id} is closed - records can no longer be added or changed"
        if transition.status == "Closed"
        else None
    )
    result: dict[str, str | None] = {}
    for perm in TRANSITION_PERMS:
        if perm is Perm.EDIT_TRANSITION and user.role == "ADMIN":
            reason = None
        else:
            reason = transition_denial(db, user, transition, perm)
        result[perm.value] = reason if reason is not None else closed_reason
    return result
