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
  ``changes`` may only hold TransitionUpdateIn keys and never tier, gate or status. Perm.CREATE_TRANSITION.
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

from typing import Any

from sqlalchemy.orm import Session

from app.models import OrionProposal, User
from app.schemas.orion import AcceptOut, ProposalKind, ProposalOut

PROPOSAL_PERMISSION: dict[str, str] = {
    "create_action": "manage_actions",
    "draft_chaser": "send_drafts",
    "request_inputs": "send_drafts",
    "request_exception": "request_exception",
    "request_approval": "send_drafts",
    "accept_applicability": "confirm_scope",
    "create_transition": "create_transition",
    "update_transition": "create_transition",
    "update_item": "update_bt_status",
    "add_evidence": "manage_evidence",
}


def create_proposal(
    db: Session,
    *,
    kind: ProposalKind,
    title: str,
    payload: dict[str, Any],
    transition_id: str | None,
) -> OrionProposal:
    """Insert an Open ``OrionProposal`` (flush, no commit; no audit - it changes no business data).
    Validates ``payload`` has the keys listed on ``ProposalOut`` for ``kind`` (ValueError otherwise).
    De-duplicates: an Open proposal with the same transition, kind and payload is returned instead.
    """
    raise NotImplementedError("M8")


def proposal_out(db: Session, proposal: OrionProposal, user: User) -> ProposalOut:
    """Map a row to ``ProposalOut``; ``can_accept``/``accept_denied_reason`` come from
    ``permissions.has_perm(user.role, <perm of the kind>)``; a non-Open proposal has can_accept False
    with reason "Already accepted" / "Already dismissed"."""
    raise NotImplementedError("M8")


def list_proposals(
    db: Session, user: User, *, transition_id: str | None, status: str | None
) -> list[ProposalOut]:
    """Newest first (created_at desc, id desc). Filters optional."""
    raise NotImplementedError("M8")


def accept_proposal(db: Session, proposal_id: int, user: User) -> AcceptOut:
    """Execute the proposal's NORMAL domain operation as ``user`` (permission checks of that operation
    apply; Forbidden 403 with the reason otherwise and nothing changes). NotFound 404 for unknown id;
    Conflict 409 "Proposal is already <status>" when not Open. On success: status Accepted,
    accepted_by/accepted_at, ``result`` stored, AuditEvent entity "OrionProposal" actor_type "Human",
    actor user, note f"Accepted Orion proposal {id}". ``navigate_to``: /drafts for draft kinds,
    /transitions/<id>/assessment for create_action, /transitions/<id>/exceptions for
    request_exception, /transitions/new?proposal=<id> for create_transition,
    /transitions/<id>/assessment for update_item / add_evidence (item deep link when known),
    /transitions/<id> for update_transition, else None. Single transaction (commit by caller)."""
    raise NotImplementedError("M8")


def dismiss_proposal(db: Session, proposal_id: int, user: User) -> ProposalOut:
    """Open -> Dismissed. 404 unknown, 409 not Open. Audited as Human with note
    f"Dismissed Orion proposal {id}"."""
    raise NotImplementedError("M8")


def get_proposal(db: Session, proposal_id: int, user: User) -> ProposalOut:
    """One proposal in any status (NotFound 404 for an unknown id), ``can_accept`` for ``user``.
    Read-only; used by the pre-filled intake form (``/transitions/new?proposal=<id>``)."""
    raise NotImplementedError("M8")
