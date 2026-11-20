"""Orion drafts (assistive mode, BR-050, FR-071). Implemented in M5.

Drafts are only ever created by Orion or a workflow rule; a permitted human edits and clicks Send.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.access import ensure_transition_role
from app.config import get_settings
from app.domain import audit
from app.domain.approvals import chain_type_for_gate, default_approver
from app.domain.html_sanitize import sanitize_html
from app.domain.notify import message_templates
from app.errors import BadRequest, Conflict, Forbidden
from app.models import (
    ApprovalChainConfig,
    ApprovalRequest,
    ExceptionRecord,
    OrionDraft,
    OutboxMessage,
    Transition,
    TransitionItem,
    User,
)
from app.permissions import DENIAL_REASONS, Perm, has_perm
from app.rules.constants import DECISION_GATES, DONE_STATUSES, GATE_SHORT, NA_STATUSES
from app.services.factory import get_ai_service, get_mail_service, get_notification_service

_EMAIL = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")
_HREF = re.compile(r'href="([^"]+)"')
_TAG = re.compile(r"<[^>]+>")


_SENDING: set[int] = set()  # drafts whose Send is in progress (the send helper marks them Sent)


def is_being_sent(draft_id: int) -> bool:
    """True while ``send_draft`` executes the draft's action (so the action does not mark it Sent)."""
    return draft_id in _SENDING


def ensure_can_use_draft(
    db: Session,
    user: User,
    transition_id: str | None,
    *,
    allow_closed: bool = False,
) -> None:
    """Who may create / edit / send / discard a draft (BE#1): the OR focal of the draft's
    transition. A draft without a transition needs the role-level Perm.SEND_DRAFTS only."""
    transition = db.get(Transition, transition_id) if transition_id else None
    if transition is None:
        if not has_perm(user.role, Perm.SEND_DRAFTS):
            raise Forbidden(DENIAL_REASONS[Perm.SEND_DRAFTS])
        return
    ensure_transition_role(db, user, transition, Perm.SEND_DRAFTS, allow_closed=allow_closed)


def mark_sent_via_approval(
    db: Session, draft: OrionDraft, user: User, request_id: str
) -> OrionDraft:
    """Mark a draft Sent because its approval request was created (no email of its own: the chain
    notification reaches the approver, so there is exactly one approver email). Audited (Human)."""
    before = _snap(draft)
    draft.status = "Sent"
    draft.sent_by = user.id
    draft.sent_at = clock.now()
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="OrionDraft",
        entity_id=draft.id,
        action="sent",
        transition_id=draft.transition_id,
        before=before,
        after={**_snap(draft), "approval_request_id": request_id},
        note=f"Draft sent via approval request {request_id}",
    )
    return draft


def _snap(draft: OrionDraft) -> dict[str, Any]:
    return audit.snapshot(draft, ["status", "to", "cc", "subject", "kind"])


def create_draft(
    db: Session,
    *,
    kind: str,
    transition: Transition | None,
    to: list[str],
    cc: list[str],
    subject: str,
    body_html: str,
    created_source: str,
    rule_id: str | None = None,
    action: dict[str, Any] | None = None,
    related_ids: Sequence[str] = (),
) -> OrionDraft:
    """Insert an OrionDraft with status Draft and audit it (actor_type == created_source).
    Nothing is sent. Does not commit.
    """
    draft = OrionDraft(
        transition_id=transition.id if transition else None,
        kind=kind,
        to=list(dict.fromkeys(to)),
        cc=[c for c in dict.fromkeys(cc) if c not in to],
        subject=subject[:300],
        body_html=sanitize_html(body_html),
        rule_id=rule_id,
        status="Draft",
        created_source=created_source,
        action=action,
        related_ids=list(related_ids),
    )
    db.add(draft)
    db.flush()
    audit.record(
        db,
        actor=None,
        actor_type=created_source if created_source in audit.ACTOR_TYPES else "System",
        entity="OrionDraft",
        entity_id=draft.id,
        action="drafted",
        transition_id=draft.transition_id,
        after=_snap(draft),
        note=f"{kind} drafted" + (f" by rule {rule_id}" if rule_id else "") + "; not sent",
    )
    return draft


def validate_addresses(to: Sequence[str], cc: Sequence[str]) -> tuple[list[str], list[str]]:
    """Trim and validate recipients (422 when ``to`` is empty or an address is malformed)."""
    to_clean = [a.strip() for a in to if a and a.strip()]
    cc_clean = [a.strip() for a in cc if a and a.strip()]
    if not to_clean:
        raise BadRequest("Recipients are required", ["Add at least one recipient in To"])
    bad = [a for a in [*to_clean, *cc_clean] if not _EMAIL.match(a)]
    if bad:
        raise BadRequest("Invalid email address", [f"Not a valid email address: {a}" for a in bad])
    return list(dict.fromkeys(to_clean)), list(dict.fromkeys(cc_clean))


def edit_draft(
    db: Session,
    *,
    draft: OrionDraft,
    user: User,
    to: Sequence[str],
    cc: Sequence[str],
    subject: str,
    body_html: str,
) -> OrionDraft:
    """Edit a Draft before sending (409 otherwise); the body is sanitised. Audited as Human.
    Only the OR focal of the draft's transition may edit it (BE#1)."""
    ensure_can_use_draft(db, user, draft.transition_id)
    if draft.status != "Draft":
        raise Conflict(
            f"Draft is {draft.status}", [f"Only a Draft can be edited (this one is {draft.status})"]
        )
    to_clean, cc_clean = validate_addresses(to, cc)
    before = _snap(draft)
    draft.to = to_clean
    draft.cc = cc_clean
    draft.subject = subject.strip()[:300]
    draft.body_html = sanitize_html(body_html)
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="OrionDraft",
        entity_id=draft.id,
        action="edited",
        transition_id=draft.transition_id,
        before=before,
        after=_snap(draft),
        note="Draft edited before sending",
    )
    return draft


def discard_draft(db: Session, *, draft: OrionDraft, user: User) -> OrionDraft:
    """Discard a Draft (never sent). 409 unless Draft. Audited as Human. Only the OR focal of the
    draft's transition may discard it (BE#1); a closed transition's drafts can still be cleared."""
    ensure_can_use_draft(db, user, draft.transition_id, allow_closed=True)
    if draft.status != "Draft":
        raise Conflict(
            f"Draft is {draft.status}",
            [f"Only a Draft can be discarded (this one is {draft.status})"],
        )
    before = _snap(draft)
    draft.status = "Discarded"
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="OrionDraft",
        entity_id=draft.id,
        action="discarded",
        transition_id=draft.transition_id,
        before=before,
        after=_snap(draft),
        note=f"Discarded Orion draft {draft.id}",
    )
    return draft


def _plain(body_html: str) -> str:
    text = re.sub(r"</(p|li|h3|h4|div|tr)>|<br>", "\n", body_html)
    return html.unescape(_TAG.sub("", text)).strip()


def _teams_card(draft: OrionDraft) -> dict[str, Any]:
    link = _HREF.search(draft.body_html)
    url = html.unescape(link.group(1)) if link else get_settings().app_base_url
    if url.startswith("/"):
        url = get_settings().app_base_url.rstrip("/") + url
    text = _plain(draft.body_html)
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            {"type": "TextBlock", "text": draft.subject, "weight": "Bolder", "wrap": True},
            {"type": "TextBlock", "text": text[:600], "wrap": True},
            {
                "type": "TextBlock",
                "text": "Orion recommends and drafts. People decide.",
                "isSubtle": True,
                "size": "Small",
                "wrap": True,
            },
        ],
        "actions": [{"type": "Action.OpenUrl", "title": "Open in Orion", "url": url}],
    }


def send_draft(
    db: Session, *, draft: OrionDraft, user: User
) -> tuple[OrionDraft, list[int], dict[str, Any]]:
    """Human send (BR-050). 409 if status != Draft. Executes ``draft.action`` first:
    {"type": "request_approval", "gate": g} -> ``app.domain.gate_actions.request_gate_approval``
    (result {"approval_request_id": ...}); {"type": "mark_inputs_requested", ...} -> owner modules.
    A failing action (409) aborts the send. Then sends the mock email via MailService and a Teams
    card to the recipients, sets status Sent, sent_by, sent_at, links OutboxMessage.draft_id,
    audits (actor Human). Returns (draft, outbox_message_ids, result). Does not commit.
    Only the OR focal of the draft's transition may send it (BE#1).
    """
    ensure_can_use_draft(db, user, draft.transition_id)
    if draft.status != "Draft":
        raise Conflict(
            f"Draft is {draft.status}", [f"Only a Draft can be sent (this one is {draft.status})"]
        )
    to, cc = validate_addresses(draft.to or [], draft.cc or [])
    before = _snap(draft)
    draft.body_html = sanitize_html(draft.body_html)  # VAPT: never send unsanitised markup
    result: dict[str, Any] = {}

    action = draft.action or {}
    kind = action.get("type")
    if kind == "request_approval":
        from app.domain import gate_actions  # another area; imported late (cycles)

        transition = db.get(Transition, draft.transition_id) if draft.transition_id else None
        if transition is None or not action.get("gate"):
            raise BadRequest("Draft action is incomplete", ["The draft has no transition or gate"])
        _SENDING.add(draft.id)
        try:
            request = gate_actions.request_gate_approval(
                db,
                transition=transition,
                gate=str(action["gate"]),
                user=user,
                note=f"Sent Orion draft {draft.id}",
                via_draft_id=draft.id,
            )
        finally:
            _SENDING.discard(draft.id)
        result["approval_request_id"] = request.id

    mailbox = get_settings().orion_mailbox
    related = list(draft.related_ids or [])
    message_ids = [
        get_mail_service(db).send_mail(mailbox, to, cc, draft.subject, draft.body_html, related)
    ]
    db.flush()
    # An approval-request draft: the chain already posted the approver's actionable approval card
    # (and the OR focal needs none), so no second, generic Teams card.
    known = (
        []
        if kind == "request_approval"
        else db.scalars(select(User).where(User.email.in_([*to, *cc]))).all()
    )
    if known:
        message_ids.append(
            get_notification_service(db).post_teams_card(
                [u.id for u in known], _teams_card(draft), draft.subject, related
            )
        )
        db.flush()
    for message_id in message_ids:
        message = db.get(OutboxMessage, message_id)
        if message is not None:
            message.draft_id = draft.id

    draft.status = "Sent"
    draft.sent_by = user.id
    draft.sent_at = clock.now()
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="OrionDraft",
        entity_id=draft.id,
        action="sent",
        transition_id=draft.transition_id,
        before=before,
        after={**_snap(draft), **result},
        note=f"Sent Orion draft {draft.id}",
    )
    return draft, message_ids, result


# --------------------------------------------------------------------------- Orion drafting


def _or_focal(db: Session, transition: Transition) -> User | None:
    return db.get(User, transition.or_focal_user_id)


def _days_to_decision(transition: Transition) -> int | None:
    if transition.next_decision_date is None:
        return None
    return (transition.next_decision_date - clock.today()).days


def _chaser_recipient(
    db: Session, row: TransitionItem, waiting: dict[str, str], item_id: str
) -> User | None:
    """Who a chaser about this item goes to: the item owner, or - when the item waits for a
    decision on a pending exception - the approver of that exception (recorded in ``waiting``)."""
    from app.domain.approvals import pending_approver  # another area; imported late

    record = db.scalars(
        select(ExceptionRecord).where(
            ExceptionRecord.transition_item_id == row.id,
            ExceptionRecord.status.like("Pending%"),
        )
    ).first()
    request = db.get(ApprovalRequest, record.approval_request_id) if record else None
    approver = pending_approver(db, request) if request is not None else None
    if record is not None and approver is not None:
        waiting[item_id] = record.ref
        return approver
    return db.get(User, row.owner_user_id) if row.owner_user_id else None


def draft_chaser(
    db: Session,
    *,
    transition: Transition,
    item_ids: Sequence[str],
    user: User | None = None,
) -> OrionDraft:
    """Orion drafts a chaser for open items (spec 10.1). 422 for unknown or Done items.
    When ``user`` (the human who asked) is given, only the transition's OR focal may ask (BE#1)."""
    if user is not None:
        ensure_can_use_draft(db, user, transition.id)
    wanted = list(dict.fromkeys(item_ids))
    db.flush()
    rows = {
        r.playbook_item_id: r
        for r in db.scalars(
            select(TransitionItem).where(
                TransitionItem.transition_id == transition.id,
                TransitionItem.playbook_item_id.in_(wanted),
            )
        ).all()
    }
    missing = [i for i in wanted if i not in rows]
    if missing:
        raise BadRequest(
            "Unknown items", [f"{i} is not an item of {transition.id}" for i in missing]
        )
    closed = [
        i
        for i in wanted
        if rows[i].status in DONE_STATUSES
        or rows[i].status in NA_STATUSES
        or rows[i].applicability == "Not applicable"
    ]
    if closed:
        raise BadRequest(
            "Items are already done", [f"{i} is already done or not applicable" for i in closed]
        )

    owners: dict[str, User] = {}
    waiting_on_exception: dict[str, str] = {}  # item id -> exception ref waiting for a decision
    for i in wanted:
        owner = _chaser_recipient(db, rows[i], waiting_on_exception, i)
        if owner is not None:
            owners.setdefault(owner.id, owner)
    focal = _or_focal(db, transition)
    to = [o.email for o in owners.values()] or ([focal.email] if focal else [])
    cc = [focal.email] if focal and focal.email not in to else []

    items_ctx = []
    for i in wanted:
        row = rows[i]
        owner = db.get(User, row.owner_user_id) if row.owner_user_id else None
        title = row.playbook_item.title
        if i in waiting_on_exception:
            title += f" - exception {waiting_on_exception[i]} is waiting for your approval"
        items_ctx.append(
            {
                "id": i,
                "title": title,
                "due_gate_short": GATE_SHORT.get(row.due_gate, row.due_gate),
                "owner_name": owner.name if owner else "",
            }
        )
    ctx = {
        "transition_id": transition.id,
        "transition_name": transition.name,
        "gate_short": GATE_SHORT.get(transition.current_gate, transition.current_gate),
        "days": _days_to_decision(transition),
        "or_focal_name": focal.name if focal else "",
        "recipient_name": next(iter(owners.values())).name if len(owners) == 1 else "",
        "items": items_ctx,
        "templates": message_templates(db),
    }
    text = get_ai_service().draft_message("chaser", ctx)
    return create_draft(
        db,
        kind="Chaser",
        transition=transition,
        to=to,
        cc=cc,
        subject=text["subject"],
        body_html=text["body_html"],
        created_source="Orion agent",
        related_ids=[transition.id, *wanted],
    )


def draft_approval_request(
    db: Session, *, transition: Transition, gate: str, user: User
) -> OrionDraft:
    """Orion drafts the AtD/AtO request email for the first approver (BR-050: nothing is sent).
    Only the transition's OR focal may ask for it (BE#1)."""
    ensure_can_use_draft(db, user, transition.id)
    if gate not in DECISION_GATES:
        raise BadRequest("Not an approval gate", [f"{gate} is not an approval gate (AtD or AtO)"])
    from app.domain.readiness_check import compute_readiness_check  # another area; imported late

    check = compute_readiness_check(db, transition, gate, user)
    if not check.can_request_approval:
        raise Conflict(
            "Approval cannot be requested yet",
            [check.request_denied_reason or f"{GATE_SHORT[gate]} is not ready for approval"],
        )
    chain_type = chain_type_for_gate(db, gate) or ""
    pending = db.scalars(
        select(ApprovalRequest).where(
            ApprovalRequest.transition_id == transition.id,
            ApprovalRequest.type == chain_type,
            ApprovalRequest.gate == gate,
            ApprovalRequest.status == "Pending",
        )
    ).first()
    if pending is not None:
        raise Conflict(
            "Approval already requested", [f"{pending.id} is already pending for this gate"]
        )
    to, cc, text = approval_request_message(db, transition, gate, user, check=check)
    return create_draft(
        db,
        kind="Approval request",
        transition=transition,
        to=to,
        cc=cc,
        subject=text["subject"],
        body_html=text["body_html"],
        created_source="Orion agent",
        action={"type": "request_approval", "gate": gate},
        related_ids=[transition.id],
    )


def approval_request_message(
    db: Session,
    transition: Transition,
    gate: str,
    user: User,
    *,
    check: Any = None,
) -> tuple[list[str], list[str], dict[str, str]]:
    """Addressing and text of the approval-request message for a decision gate: To = the approver
    of the chain's first step (from the chain definition, e.g. AtD -> the transition's OLM), Cc = the
    OR focal. Shared by the "Request approval" draft (M5) and rule R4's "Ready for <gate>" draft, so
    the message the OR focal sends IS the approval request. ``user`` is only used to evaluate the
    readiness check (read-only). Returns (to, cc, {"subject", "body_html"})."""
    from app.domain.readiness_check import compute_readiness_check  # another area; imported late

    if check is None:
        check = compute_readiness_check(db, transition, gate, user)
    chain_type = chain_type_for_gate(db, gate) or ""
    config = db.get(ApprovalChainConfig, chain_type)
    first_role = sorted(config.steps, key=lambda s: s["step"])[0]["role"] if config else "OLM"
    approver_id = default_approver(db, transition, first_role)
    approver = db.get(User, approver_id) if approver_id else None
    focal = _or_focal(db, transition)
    to = [approver.email] if approver else ([focal.email] if focal else [])
    cc = [focal.email] if focal and focal.email not in to else []
    ctx = {
        "transition_id": transition.id,
        "transition_name": transition.name,
        "gate": gate,
        "gate_short": GATE_SHORT[gate],
        "days": _days_to_decision(transition),
        "verdict": check.verdict_label,
        # The message is addressed to the approver, so the "First approver: <role>" line is left out.
        "approver_role": "",
        "recipient_name": approver.name if approver else "",
        "or_focal_name": focal.name if focal else "",
        "summary": check.narrative,
        "templates": message_templates(db),
    }
    return to, cc, get_ai_service().draft_message("approval request", ctx)
