"""Orion proposals (BR-050, NFR-04): stored recommendation cards that only a permitted human executes.

NFR-04 / BR-050 INVARIANT: the Orion service (AIService, chat, insights, proposal creation) has NO
write path to statuses, applicability, tiers, evidence acceptance, conditions, approvals or gate
decisions. ``create_proposal`` only inserts an ``OrionProposal`` row. ``accept_proposal`` calls the
NORMAL domain operation as the CURRENT USER (so that operation's permission and validation rules apply)
and audits with actor_type "Human".

Required test (builder): (1) static check - no module under ``app/services`` or
``domain/orion_chat.py`` imports a mutating domain function except ``domain.reminders.run_reminders``
(drafts only) and ``domain.proposals.create_proposal``; (2) behavioural - call POST /orion/chat with
every quick action and free text, assert counts of item statuses/applicability, transition tier,
evidence, conditions, approval requests, gate decisions and non-Human AuditEvents are unchanged (only
OrionDraft/OrionProposal/ReminderRun/LeadershipUpdate rows may appear); (3) a user without the
permission accepting gets 403 and the proposal stays Open.

Kind -> operation executed on accept (permission of that operation applies):
create_action -> actions create (result {action_id}); draft_chaser -> ``domain.drafts.draft_chaser``
(Perm.SEND_DRAFTS, {draft_id}); request_inputs -> input-request draft (Perm.SEND_DRAFTS, {draft_id});
request_exception -> exception request (result {exception_id}); request_approval ->
``domain.drafts.draft_approval_request`` (Perm.SEND_DRAFTS, {draft_id}); accept_applicability ->
the scope accept-decisions operation ({accepted: n}).

Natural-language kinds (``schemas.orion.PAYLOAD_MODELS``), all still "Orion drafts, a human clicks":
* create_transition -> HAND-OFF. Accept calls NO domain operation and creates nothing: it marks the
  proposal Accepted (result {"handoff": true}), audits it, and returns navigate_to
  ``/transitions/new?proposal=<id>``. The intake form loads the payload with GET /orion/proposals/{id},
  shows the banner and the human clicks Create (POST /transitions, Perm.CREATE_TRANSITION). Permission
  checked at Accept (can_accept): Perm.CREATE_TRANSITION.
* update_transition -> ``domain.intake.update_transition`` (PATCH rules, 409 closed, 422 validation).
  ``changes`` may only hold TransitionUpdateIn keys and never tier, gate or status. Perm.EDIT_TRANSITION
  (the OR focal of the transition; an Admin may re-assign people).
* update_item -> ``domain.items.patch_item`` with ``changes`` (status only for Business/Technical items;
  per-field permission exactly as PATCH /items/{id}: owner/note/status UPDATE_BT_STATUS, a Compliance
  item's owner/note UPDATE_C_STATUS or current owner). Item payload is re-validated on accept (item
  still exists, status still allowed, current value unchanged -> else 409 "Item changed since Orion
  proposed this"). The audit actor is Human and last_updated_source "Human" (not "Orion agent").
* add_evidence -> ``domain.evidence.add_evidence`` type Link / Email sign-off, status Submitted
  (acceptance remains Perm.REVIEW_EVIDENCE_*). Perm.MANAGE_EVIDENCE.

``proposal_out`` computes ``can_accept`` from the kind's permission (``PROPOSAL_PERMISSION`` below);
for update_item the permission depends on the item's lens and the changed fields.

Extra validation in ``create_proposal`` for the new kinds: payload parsed with ``PAYLOAD_MODELS[kind]``
(ValueError on failure); ids exist (users, transition, item); no payload may contain keys outside the
whitelist of the kind (prevents smuggling e.g. ``tier`` or ``applicability`` into update_transition /
update_item). ``transition_id`` is None only for create_transition.

``GET /orion/proposals/{id}`` (``get_proposal``) is readable by any signed-in user for any status, so the
pre-filled intake form still opens after Accept or a page reload.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.access import ensure_open, is_assigned, transition_denial
from app.domain import audit
from app.errors import Conflict, Forbidden, NotFound
from app.models import OrionProposal, Transition, TransitionItem, User
from app.permissions import DENIAL_REASONS, Perm, has_perm
from app.rules.constants import ACTOR_HUMAN, DECISION_GATES, STATUSES_BY_LENS
from app.schemas.common import PersonRef
from app.schemas.intake import TransitionCreateIn, TransitionUpdateIn
from app.schemas.orion import PAYLOAD_MODELS, AcceptOut, ProposalKind, ProposalOut

PROPOSAL_PERMISSION: dict[str, str] = {
    "create_action": "manage_actions",
    "draft_chaser": "send_drafts",
    "request_inputs": "send_drafts",
    "request_exception": "request_exception",
    "request_approval": "send_drafts",
    "accept_applicability": "confirm_scope",
    "create_transition": "create_transition",
    "update_transition": "edit_transition",
    "update_item": "update_bt_status",
    "add_evidence": "manage_evidence",
}

# Keys each kind must carry (ProposalOut.payload comment); the four natural-language kinds are
# validated against PAYLOAD_MODELS instead.
_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "create_action": ("title", "item_ids", "owner_user_id", "due_date", "priority"),
    "draft_chaser": ("item_ids",),
    "request_inputs": ("version_id", "line_ids"),
    "request_exception": ("item_id", "text"),
    "request_approval": ("gate",),
    "accept_applicability": ("decisions",),
}
_ITEM_CHANGE_KEYS = frozenset({"status", "gap_severity", "note", "owner_user_id"})
_FORBIDDEN_TRANSITION_KEYS = frozenset(
    {"risk_tier", "tier", "current_gate", "status", "tier_status"}
)
CLOSED_REASON = "{tid} is closed - records can no longer be added or changed"
# Who asked Orion for the proposal. Kept inside the JSON payload (no schema change) and never
# returned by the API; a proposal is its creator's private draft output (BR-050).
CREATOR_KEY = "_created_by"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _item_of(db: Session, transition_id: str, item_id: str) -> TransitionItem | None:
    return db.scalars(
        select(TransitionItem).where(
            TransitionItem.transition_id == transition_id,
            TransitionItem.playbook_item_id == item_id,
        )
    ).first()


def _validate_payload(
    db: Session, kind: str, payload: dict[str, Any], transition_id: str | None
) -> dict[str, Any]:
    """Normalised payload, or ValueError (a payload can never smuggle tier, status or applicability)."""
    if kind not in PROPOSAL_PERMISSION:
        raise ValueError(f"Unknown proposal kind '{kind}'")
    if (transition_id is None) != (kind == "create_transition"):
        raise ValueError("transition_id is required for every kind except create_transition")
    if transition_id is not None and db.get(Transition, transition_id) is None:
        raise ValueError(f"Unknown transition '{transition_id}'")
    payload = json.loads(_canonical(payload))
    if kind in _REQUIRED_KEYS:
        missing = [k for k in _REQUIRED_KEYS[kind] if k not in payload]
        if missing:
            raise ValueError(f"Payload of {kind} is missing: {', '.join(missing)}")
        if kind == "create_action" and db.get(User, payload["owner_user_id"]) is None:
            raise ValueError("Unknown owner")
        if kind == "request_approval" and payload["gate"] not in DECISION_GATES:
            raise ValueError("request_approval needs an AtD or AtO gate")
        return payload  # type: ignore[no-any-return]
    model: type[BaseModel] = PAYLOAD_MODELS[kind]
    unknown = set(payload) - set(model.model_fields)
    if unknown:
        raise ValueError(f"Unexpected payload keys: {', '.join(sorted(unknown))}")
    parsed = model(**payload)
    clean: dict[str, Any] = parsed.model_dump(mode="json")
    if kind == "create_transition":
        extra = set(clean["prefill"]) - set(TransitionCreateIn.model_fields)
        if extra:
            raise ValueError(f"Unexpected prefill keys: {', '.join(sorted(extra))}")
    elif kind == "update_transition":
        keys = set(clean["changes"])
        if keys & _FORBIDDEN_TRANSITION_KEYS or keys - set(TransitionUpdateIn.model_fields):
            raise ValueError("update_transition may only change intake fields (never tier or gate)")
        if clean["transition_id"] != transition_id:
            raise ValueError("Payload transition does not match the proposal")
    elif kind == "update_item":
        keys = set(clean["changes"])
        if not keys or keys - _ITEM_CHANGE_KEYS:
            raise ValueError("update_item may only change status, gap severity, note or owner")
        row = _item_of(db, clean["transition_id"], clean["item_id"])
        if row is None or clean["transition_id"] != transition_id:
            raise ValueError("Unknown item")
        lens = row.playbook_item.lens
        if "status" in keys:
            if lens == "Compliance":
                raise ValueError("Orion never proposes a Compliance status")
            if clean["changes"]["status"] not in STATUSES_BY_LENS[lens]:
                raise ValueError("Status not allowed for this lens")
        if "owner_user_id" in keys and db.get(User, clean["changes"]["owner_user_id"]) is None:
            raise ValueError("Unknown owner")
    elif kind == "add_evidence":
        if clean["transition_id"] != transition_id:
            raise ValueError("Payload transition does not match the proposal")
        if clean["item_id"] and _item_of(db, transition_id or "", clean["item_id"]) is None:
            raise ValueError("Unknown item")
        if clean["type"] == "Link" and not clean.get("url"):
            raise ValueError("A link needs a url")
        if clean["type"] == "Email sign-off" and not (clean.get("text") or "").strip():
            raise ValueError("An email sign-off needs the pasted text")
    return clean


def create_proposal(
    db: Session,
    *,
    kind: ProposalKind,
    title: str,
    payload: dict[str, Any],
    transition_id: str | None,
    created_by: str | None = None,
) -> OrionProposal:
    """Insert an Open ``OrionProposal`` (flush, no commit; no audit - it changes no business data).
    Validates ``payload`` has the keys listed on ``ProposalOut`` for ``kind`` (ValueError otherwise).
    De-duplicates: an Open proposal with the same transition, kind and payload is returned instead.
    """
    clean = _validate_payload(db, kind, payload, transition_id)
    existing = db.scalars(
        select(OrionProposal).where(
            OrionProposal.kind == kind,
            OrionProposal.status == "Open",
            (
                OrionProposal.transition_id.is_(None)
                if transition_id is None
                else OrionProposal.transition_id == transition_id
            ),
        )
    ).all()
    if created_by:
        clean[CREATOR_KEY] = created_by
    wanted = _canonical(clean)
    for row in existing:
        if _canonical(row.payload) == wanted:
            return row
    row = OrionProposal(
        transition_id=transition_id,
        kind=kind,
        title=title[:2000],
        payload=clean,
        status="Open",
        created_at=clock.now(),
    )
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------------------------
def _item_denial(db: Session, user: User, row: OrionProposal, t: Transition) -> str | None:
    item = _item_of(db, t.id, row.payload["item_id"])
    if item is None:
        return f"{row.payload['item_id']} is no longer an item of {t.id}"
    if item.playbook_item.lens == "Compliance":
        if user.id == item.owner_user_id:
            return None
        return transition_denial(db, user, t, Perm.UPDATE_C_STATUS)
    return transition_denial(db, user, t, Perm.UPDATE_BT_STATUS)


def accept_denial(db: Session, user: User, row: OrionProposal) -> str | None:
    """None when ``user`` may accept ``row``, else the reason (tooltip / 403). Uses the same
    per-transition rule as the underlying operation (``app.access``)."""
    if row.status != "Open":
        return f"Already {row.status.lower()}"
    if row.kind == "create_transition":
        perm = Perm.CREATE_TRANSITION
        return None if has_perm(user.role, perm) else DENIAL_REASONS[perm]
    t = db.get(Transition, row.transition_id) if row.transition_id else None
    if t is None:
        return "The transition no longer exists"
    if row.kind == "update_transition":
        # An Admin may only re-assign people (R-01); any other change needs the OR focal.
        people = {
            "or_focal_user_id",
            "pm_user_id",
            "architect_user_id",
            "olm_user_id",
            "irm_user_id",
        }
        changes = set((row.payload or {}).get("changes", {}))
        reason = (
            None
            if user.role == "ADMIN" and changes and changes <= people
            else transition_denial(db, user, t, Perm.EDIT_TRANSITION)
        )
    elif row.kind == "update_item":
        reason = _item_denial(db, user, row, t)
    else:
        reason = transition_denial(db, user, t, Perm(PROPOSAL_PERMISSION[row.kind]))
    if reason is None and t.status == "Closed":
        return CLOSED_REASON.format(tid=t.id)
    return reason


def proposal_out(db: Session, proposal: OrionProposal, user: User) -> ProposalOut:
    """Map a row to ``ProposalOut``; ``can_accept``/``accept_denied_reason`` come from the access rule
    of the kind (``app.access``); a non-Open proposal has can_accept False with reason
    "Already accepted" / "Already dismissed"."""
    reason = accept_denial(db, user, proposal)
    if reason is not None and proposal.status != "Open":
        reason = f"Already {proposal.status.lower()}"
    accepted_by = db.get(User, proposal.accepted_by) if proposal.accepted_by else None
    return ProposalOut(
        id=proposal.id,
        transition_id=proposal.transition_id,
        kind=proposal.kind,  # type: ignore[arg-type]
        title=proposal.title,
        payload={k: v for k, v in (proposal.payload or {}).items() if k != CREATOR_KEY},
        status=proposal.status,  # type: ignore[arg-type]
        created_at=proposal.created_at,
        accepted_by=PersonRef(id=accepted_by.id, name=accepted_by.name) if accepted_by else None,
        accepted_at=proposal.accepted_at,
        can_accept=reason is None,
        accept_denied_reason=reason,
    )


def can_view(db: Session, user: User, row: OrionProposal) -> bool:
    """A proposal is visible to its creator, an Admin, and (for transition-bound kinds) the people
    assigned to that transition. A create_transition prefill (pasted source text) is private to its
    creator. Rows without a recorded creator (older data) stay visible to every signed-in user."""
    creator = (row.payload or {}).get(CREATOR_KEY)
    if creator is None or creator == user.id or user.role == "ADMIN":
        return True
    t = db.get(Transition, row.transition_id) if row.transition_id else None
    return t is not None and is_assigned(user, t)


def list_proposals(
    db: Session, user: User, *, transition_id: str | None, status: str | None
) -> list[ProposalOut]:
    """Newest first (created_at desc, id desc). Filters optional. Only proposals ``user`` may see."""
    query = select(OrionProposal)
    if transition_id:
        query = query.where(OrionProposal.transition_id == transition_id)
    if status:
        query = query.where(OrionProposal.status == status)
    rows = db.scalars(
        query.order_by(OrionProposal.created_at.desc(), OrionProposal.id.desc())
    ).all()
    return [proposal_out(db, r, user) for r in rows if can_view(db, user, r)]


def get_proposal(db: Session, proposal_id: int, user: User) -> ProposalOut:
    """One proposal in any status (NotFound 404 for an unknown id), ``can_accept`` for ``user``.
    Read-only; used by the pre-filled intake form (``/transitions/new?proposal=<id>``)."""
    return proposal_out(db, _load(db, proposal_id, user), user)


def _load(db: Session, proposal_id: int, user: User | None = None) -> OrionProposal:
    row = db.get(OrionProposal, proposal_id)
    if row is None or (user is not None and not can_view(db, user, row)):
        raise NotFound(f"Proposal {proposal_id} not found")
    return row


# ---------------------------------------------------------------------------------------------
# Accept / dismiss
# ---------------------------------------------------------------------------------------------
def _execute(
    db: Session, user: User, row: OrionProposal, t: Transition | None
) -> tuple[dict[str, Any], str | None]:
    """Run the NORMAL domain operation as ``user``; returns (result, navigate_to). Imports are late:
    these modules are another area's and Orion has no import-time dependency on them (BR-050)."""
    p = row.payload
    kind = row.kind
    if kind == "create_transition":
        return {"handoff": True}, f"/transitions/new?proposal={row.id}"
    if t is None:
        raise RuntimeError("t expected")
    tid = t.id
    if kind == "create_action":
        from app.domain.records import create_action
        from app.schemas.records import ActionCreateIn

        out = create_action(
            db,
            tid,
            ActionCreateIn(
                title=p["title"],
                item_ids=p.get("item_ids") or [],
                owner_user_id=p["owner_user_id"],
                due_date=date.fromisoformat(p["due_date"]),
                priority=p.get("priority") or "Medium",
            ),
            user,
        )
        return {"action_id": out.id}, f"/transitions/{tid}/gaps?action={out.id}"
    if kind == "draft_chaser":
        from app.domain.drafts import draft_chaser

        draft = draft_chaser(db, transition=t, item_ids=p["item_ids"])
        return {"draft_id": draft.id}, "/drafts"
    if kind == "request_inputs":
        from app.domain import ocet

        version = ocet.get_version(db, int(p["version_id"]))
        if version.estimate.transition_id != tid:
            raise Conflict("The OCET version belongs to another transition")
        draft_ids, requested = ocet.request_inputs(
            db, version, [int(i) for i in p["line_ids"]], user
        )
        if not draft_ids:
            raise Conflict("No input request could be drafted")
        return {
            "draft_id": draft_ids[0],
            "draft_ids": draft_ids,
            "lines": len(requested),
        }, "/drafts"
    if kind == "request_exception":
        from app.routers.exceptions import create_exception  # the operation lives in the router
        from app.schemas.exceptions import ExceptionCreateIn

        out = create_exception(
            tid, ExceptionCreateIn(item_id=p["item_id"], text=p["text"]), user, db
        )
        return {"exception_id": out.ref}, f"/transitions/{tid}/conditions"
    if kind == "request_approval":
        from app.domain.drafts import draft_approval_request

        draft = draft_approval_request(db, transition=t, gate=p["gate"], user=user)
        return {"draft_id": draft.id}, "/drafts"
    if kind == "accept_applicability":
        from app.domain import scope as scope_domain
        from app.schemas.scope import ScopeDecisionIn, ScopeUpdateIn

        decisions = [
            ScopeDecisionIn(item_id=d["item_id"], applies=d["applies"], reason=d.get("reason"))
            for d in p["decisions"]
        ]
        scope_domain.update_scope(
            db, user, t, ScopeUpdateIn(decisions=decisions, source="orion_recommendation")
        )
        return {"accepted": len(decisions)}, f"/transitions/{tid}/scope"
    if kind == "update_transition":
        from app.domain.intake import update_transition

        before = {k: getattr(t, k, None) for k in p["changes"]}
        update_transition(db, user, t, TransitionUpdateIn(**p["changes"]))
        changed = [k for k in p["changes"] if before[k] != getattr(t, k, None)]
        return {"transition_id": tid, "changed": changed}, f"/transitions/{tid}"
    if kind == "update_item":
        from app.domain.items import patch_item
        from app.schemas.items import ItemPatchIn

        item = _item_of(db, tid, p["item_id"])
        if item is None:
            raise Conflict("Item changed since Orion proposed this", ["The item no longer exists"])
        stale = [k for k, v in (p.get("current") or {}).items() if getattr(item, k, None) != v]
        if stale:
            raise Conflict(
                "Item changed since Orion proposed this",
                [f"{p['item_id']}: {', '.join(stale)} changed - ask Orion again"],
            )
        before = {k: getattr(item, k, None) for k in p["changes"]}
        patch_item(db, item.id, ItemPatchIn(**p["changes"]), user)
        db.refresh(item)
        changed = [k for k in p["changes"] if before[k] != getattr(item, k, None)]
        return {"item_id": p["item_id"], "changed": changed}, (
            f"/transitions/{tid}/assessment?item={p['item_id']}"
        )
    if kind == "add_evidence":
        from app.domain.evidence import add_evidence

        out = add_evidence(
            db,
            tid,
            title=p["title"],
            type=p["type"],
            item_id=p.get("item_id"),
            url=p.get("url"),
            text=p.get("text"),
            filename=None,
            content=None,
            user=user,
        )
        link = f"?item={p['item_id']}" if p.get("item_id") else ""
        return {"evidence_id": out.id}, f"/transitions/{tid}/evidence{link}"
    raise ValueError(f"Unknown proposal kind '{kind}'")  # pragma: no cover


def _raise_denied(db: Session, row: OrionProposal, reason: str) -> None:
    """403 with the reason, except a closed transition which is 409 like every other write."""
    t = db.get(Transition, row.transition_id) if row.transition_id else None
    if t is not None and reason == CLOSED_REASON.format(tid=t.id):
        ensure_open(t)
    raise Forbidden(reason)


def accept_proposal(db: Session, proposal_id: int, user: User) -> AcceptOut:
    """Execute the proposal's NORMAL domain operation as ``user`` (permission checks of that operation
    apply; Forbidden 403 with the reason otherwise and nothing changes). NotFound 404 for unknown id;
    Conflict 409 "Proposal is already <status>" when not Open. On success: status Accepted,
    accepted_by/accepted_at, ``result`` stored, AuditEvent entity "OrionProposal" actor_type "Human",
    actor user, note f"Accepted Orion proposal {id}". ``navigate_to``: /drafts for draft kinds,
    the affected tab for the others, /transitions/new?proposal=<id> for create_transition.
    Single transaction (commit by caller)."""
    row = _load(db, proposal_id, user)
    if row.status != "Open":
        raise Conflict(f"Proposal is already {row.status.lower()}")
    reason = accept_denial(db, user, row)
    if reason is not None:
        _raise_denied(db, row, reason)
    t = db.get(Transition, row.transition_id) if row.transition_id else None
    result, navigate = _execute(db, user, row, t)
    row.status = "Accepted"
    row.accepted_by = user.id
    row.accepted_at = clock.now()
    row.result = result
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="OrionProposal",
        entity_id=row.id,
        action="accepted",
        transition_id=row.transition_id,
        before={"status": "Open"},
        after={"status": "Accepted", "kind": row.kind, "result": result},
        note=f"Accepted Orion proposal {row.id}",
    )
    return AcceptOut(proposal=proposal_out(db, row, user), result=result, navigate_to=navigate)


def dismiss_proposal(db: Session, proposal_id: int, user: User) -> ProposalOut:
    """Open -> Dismissed. 404 unknown, 409 not Open. Audited as Human with note
    f"Dismissed Orion proposal {id}". Same right as accepting (403 with the reason otherwise)."""
    row = _load(db, proposal_id, user)
    if row.status != "Open":
        raise Conflict(f"Proposal is already {row.status.lower()}")
    reason = accept_denial(db, user, row)
    if reason is not None:
        _raise_denied(db, row, reason)
    row.status = "Dismissed"
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="OrionProposal",
        entity_id=row.id,
        action="dismissed",
        transition_id=row.transition_id,
        before={"status": "Open"},
        after={"status": "Dismissed", "kind": row.kind},
        note=f"Dismissed Orion proposal {row.id}",
    )
    return proposal_out(db, row, user)
