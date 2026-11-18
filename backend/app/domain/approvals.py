"""Sequential approval chains (spec §6 ApprovalRequest, BR-041, FR-070). Implemented in M5.

Chain definition comes from ``ApprovalChainConfig`` (type -> steps [{step, role, label}]).
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.access import ensure_open
from app.config import get_settings
from app.domain import audit
from app.domain.html_sanitize import escape_text
from app.domain.ids import next_id
from app.domain.notify import deliver
from app.errors import BadRequest, Conflict, Forbidden, NotFound
from app.models import (
    ApprovalChainConfig,
    ApprovalRequest,
    ApprovalStep,
    ExceptionRecord,
    Transition,
    User,
)
from app.rules.constants import GATE_SHORT
from app.services.cards import render_card

CompletionHook = Callable[[Session, ApprovalRequest], None]
CardDataProvider = Callable[[Session, ApprovalRequest], dict[str, Any]]

TYPE_LABELS: dict[str, str] = {
    "OCET": "OCET approval",
    "AtD": "Authority to Deploy",
    "AtO": "Authority to Operate",
    "SUPPORT_MODEL": "Support model approval",
    "EXCEPTION": "Exception approval",
    "RISK_ACCEPTANCE": "Risk acceptance",
}
ROLE_LABELS: dict[str, str] = {
    "OR_FOCAL": "OR focal",
    "PM": "PM",
    "ARCHITECT": "Architect",
    "OLM": "OLM",
    "PLANNER": "Planner",
    "IRM": "IRM",
    "CISO_BISO": "CISO/BISO",
    "LEADERSHIP": "Leadership",
    "ADMIN": "Admin",
}
MOCK_ROLE = "CISO_BISO"
MOCK_APPROVER_ROLE = "IRM"  # demo mode: IRM approves the CISO/BISO step (spec 7.7)

_HOOKS: dict[str, list[CompletionHook]] = {}
_CARD_DATA: dict[str, CardDataProvider] = {}


# --------------------------------------------------------------------------- helpers


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)


def subject_link(request: ApprovalRequest) -> str:
    """Deep link (relative) to the subject of a request (spec 8.11)."""
    base = f"/transitions/{request.transition_id}"
    tab = {
        "AtD": "gates",
        "AtO": "gates",
        "EXCEPTION": "conditions",
        "OCET": "ocet",
        "SUPPORT_MODEL": "support-model",
    }.get(request.type, "gates")
    return f"{base}/{tab}"


def inbox_link(request: ApprovalRequest) -> str:
    return f"/approvals?request={request.id}"


def absolute(link: str) -> str:
    return get_settings().app_base_url.rstrip("/") + link


def current_step(request: ApprovalRequest) -> ApprovalStep | None:
    return next((s for s in request.steps if s.status == "Pending"), None)


def is_mock_step(step: ApprovalStep) -> bool:
    return step.role == MOCK_ROLE and step.approver_user_id is None


def act_denied_reason(db: Session, step: ApprovalStep, user: User) -> str | None:
    """Why ``user`` may not act on ``step`` (None = allowed). Rules of PLAN A-57.

    No Admin override (BE#1). The mocked CISO/BISO step has no person: in demo mode only the IRM
    assigned to the subject transition may approve it (BE#12)."""
    if is_mock_step(step):
        if user.role != MOCK_APPROVER_ROLE or not get_settings().demo_mode:
            return "The CISO/BISO step can be approved only by IRM (mock) in demo mode"
        request = db.get(ApprovalRequest, step.request_id)
        transition = db.get(Transition, request.transition_id) if request else None
        if transition is not None and transition.irm_user_id != user.id:
            irm = db.get(User, transition.irm_user_id) if transition.irm_user_id else None
            who = (
                f"{irm.name}, the IRM of {transition.id}" if irm else f"the IRM of {transition.id}"
            )
            return f"Only {who}, can approve the CISO/BISO step (mock)"
        return None
    if user.role != step.role:
        return f"This step needs the {role_label(step.role)} role"
    if step.approver_user_id is not None and step.approver_user_id != user.id:
        approver = db.get(User, step.approver_user_id)
        name = approver.name if approver else step.approver_user_id
        return f"This step must be approved by {name}"
    return None


def pending_status_label(step: ApprovalStep) -> str:
    """Exception status while ``step`` is pending: "Pending IRM", "Pending CISO/BISO" (EX-status).
    The label comes from the chain step role, so an Admin-edited chain changes it automatically."""
    return f"Pending {role_label(step.role)}"


def exception_status(db: Session, record: ExceptionRecord) -> str:
    """Status of an exception derived from its approval chain while it is pending."""
    if not record.status.startswith("Pending") or not record.approval_request_id:
        return record.status
    request = db.get(ApprovalRequest, record.approval_request_id)
    step = current_step(request) if request is not None and request.status == "Pending" else None
    return pending_status_label(step) if step is not None else record.status


def pending_exception_statuses(db: Session) -> list[str]:
    """Every "Pending <role>" label of the configured EXCEPTION chain (reference lists)."""
    config = db.get(ApprovalChainConfig, "EXCEPTION")
    steps = sorted(config.steps, key=lambda s: s["step"]) if config else []
    labels = [f"Pending {role_label(s['role'])}" for s in steps]
    return list(dict.fromkeys(labels))


def _snap(request: ApprovalRequest) -> dict[str, Any]:
    return {"status": request.status, "steps": {s.step: s.status for s in request.steps}}


def _actor_type(created_source: str) -> str:
    return created_source if created_source in audit.ACTOR_TYPES else "System"


def default_approver(db: Session, transition: Transition, role: str) -> str | None:
    if role == "OLM":
        return transition.olm_user_id
    if role == "IRM":
        return transition.irm_user_id
    if role == "ARCHITECT":
        return transition.architect_user_id
    if role == "PLANNER":
        return db.scalars(
            select(User.id).where(User.role == "PLANNER").order_by(User.id).limit(1)
        ).first()
    return None  # CISO_BISO (mock) and anything else


def _recipients(db: Session, transition: Transition, step: ApprovalStep) -> list[str]:
    if step.approver_user_id:
        return [step.approver_user_id]
    if is_mock_step(step):
        return [transition.irm_user_id] if transition.irm_user_id else []  # demo: IRM acts for it
    # No approver resolved: tell every user of the step role so the step is never silent (BE#12).
    return list(db.scalars(select(User.id).where(User.role == step.role).order_by(User.id)).all())


def validate_approvers(
    db: Session, chain_type: str, approvers: dict[int, str] | None
) -> dict[int, str]:
    """422 unless every {step: user_id} names a real step of the chain and a user holding the step
    role (BE#12). The mocked CISO/BISO step has no person and cannot be overridden."""
    if not approvers:
        return {}
    config = db.get(ApprovalChainConfig, chain_type)
    roles = {int(s["step"]): s["role"] for s in (config.steps if config else [])}
    reasons: list[str] = []
    for step_no, user_id in approvers.items():
        if step_no not in roles:
            reasons.append(f"The {chain_type} chain has no step {step_no}")
            continue
        role = roles[step_no]
        person = db.get(User, user_id)
        if role == MOCK_ROLE:
            reasons.append(f"Step {step_no} is the mocked CISO/BISO step - it has no approver")
        elif person is None:
            reasons.append(f"Step {step_no}: unknown user '{user_id}'")
        elif person.role != role:
            reasons.append(
                f"Step {step_no} needs a user with the {role_label(role)} role "
                f"({person.name} is {role_label(person.role)})"
            )
    if reasons:
        raise BadRequest("Invalid approvers", reasons)
    return {int(k): v for k, v in approvers.items()}


def _card(
    db: Session, request: ApprovalRequest, step: ApprovalStep, transition: Transition
) -> dict[str, Any]:
    total = len(request.steps)
    base: dict[str, Any] = {
        "request_id": request.id,
        "step": step.step,
        "step_count": total,
        "step_label": step.label,
        "transition_name": transition.name,
        "deep_link": absolute(subject_link(request)),
    }
    provider = _CARD_DATA.get(request.type)
    extra = provider(db, request) if provider else {}
    if request.type == "OCET":
        data = {
            "version": request.subject_id or "",
            "total_5y": "",
            "currency": "",
            "variance_text": request.subject_label,
            "top_categories": [],
            **base,
            **extra,
        }
        return render_card("ocet_approval", data)
    requester = db.get(User, request.created_by) if request.created_by else None
    label = TYPE_LABELS.get(request.type, request.type)
    facts = [{"title": "Type", "value": label}]
    if request.gate:
        facts.append({"title": "Gate", "value": GATE_SHORT.get(request.gate, request.gate)})
    if request.subject_label:
        facts.append({"title": "Summary", "value": request.subject_label})
    facts.append({"title": "Requested by", "value": requester.name if requester else "Orion"})
    data = {
        "title": f"{label} requested",
        "subject": request.subject_label or request.subject_id or request.type,
        "facts": facts,
        **base,
        **extra,
    }
    return render_card("approval_request", data)


def _notify_step(
    db: Session,
    request: ApprovalRequest,
    step: ApprovalStep,
    transition: Transition,
    skip_email_for: Collection[str] = (),
) -> None:
    recipients = _recipients(db, transition, step)
    if not recipients:
        return
    label = TYPE_LABELS.get(request.type, request.type)
    mock = " (mock CISO/BISO step)" if is_mock_step(step) else ""
    link = absolute(subject_link(request))
    summary = f"<br>{escape_text(request.subject_label)}" if request.subject_label else ""
    html = (
        f"<p>Your approval is needed for <strong>{escape_text(label)}</strong> on "
        f"<strong>{escape_text(transition.name)}</strong>{escape_text(mock)}.</p>"
        f"<p>Step {step.step} of {len(request.steps)}: {escape_text(step.label)}{summary}</p>"
        f'<p><a href="{escape_text(link)}">Open in Orion</a></p>'
        "<p>Orion, on behalf of the OR team</p>"
    )
    # People already addressed by a draft that is being sent get the in-app notice only (one email).
    quiet = (
        {u.id for u in db.scalars(select(User).where(User.email.in_(list(skip_email_for)))).all()}
        if skip_email_for
        else set()
    )
    loud = [uid for uid in recipients if uid not in quiet]
    text = f"{label} for {transition.name} needs your approval (step {step.step}){mock}"
    if loud:
        deliver(
            db,
            user_ids=loud,
            text=text,
            link=inbox_link(request),
            email_subject=f"Approval needed: {label} for {transition.name}",
            email_html=html,
            teams_card=_card(db, request, step, transition),
            related_ids=[transition.id, request.id],
        )
    muted = [uid for uid in recipients if uid in quiet]
    if muted:
        deliver(db, user_ids=muted, text=text, link=inbox_link(request))


def _notify_requester(
    db: Session, request: ApprovalRequest, transition: Transition, outcome: str, user: User | None
) -> None:
    if not request.created_by:
        return
    label = TYPE_LABELS.get(request.type, request.type)
    by = f" by {user.name}" if user else ""
    text = f"{label} for {transition.name} was {outcome}{by}"
    link = absolute(subject_link(request))
    deliver(
        db,
        user_ids=[request.created_by],
        text=text,
        link=subject_link(request),
        email_subject=f"{label} {outcome}: {transition.name}",
        email_html=(
            f"<p>{escape_text(text)}.</p>" f'<p><a href="{escape_text(link)}">Open in Orion</a></p>'
        ),
        related_ids=[transition.id, request.id],
    )


def _run_hooks(db: Session, request: ApprovalRequest) -> None:
    for hook in list(_HOOKS.get(request.type, [])):
        hook(db, request)


def _check_can_act(db: Session, request: ApprovalRequest, step: int, user: User) -> ApprovalStep:
    row = next((s for s in request.steps if s.step == step), None)
    if row is None:
        raise NotFound(f"Approval request {request.id} has no step {step}")
    if request.status != "Pending":
        raise Conflict(
            f"Request {request.id} is {request.status}",
            [f"The request is already {request.status}"],
        )
    if row.status != "Pending":
        cur = current_step(request)
        reason = (
            f"Step {step} is already {row.status}"
            if cur is None or cur.step > step
            else f"Step {cur.step} must be decided first (steps run in sequence)"
        )
        raise Conflict("Step is not the current step", [reason])
    reason = act_denied_reason(db, row, user)
    if reason:
        raise Forbidden(reason)
    subject = db.get(Transition, request.transition_id)
    if subject is not None:
        ensure_open(subject)  # a closed transition is frozen (BE#7)
    if user.id == request.created_by and not get_settings().demo_mode:
        raise Conflict(
            "The requester cannot approve their own request",
            ["The requester cannot approve their own request"],
        )
    return row


# --------------------------------------------------------------------------- public API


def create_approval_request(
    db: Session,
    *,
    type: str,
    transition: Transition,
    created_by: User | None,
    created_source: str,
    gate: str | None = None,
    subject_id: str | None = None,
    subject_label: str = "",
    approvers: dict[int, str] | None = None,
    skip_email_for: Collection[str] = (),
) -> ApprovalRequest:
    """Create a Pending request with one ApprovalStep per ApprovalChainConfig step.

    Approver defaults from the transition: OLM -> transition.olm_user_id, IRM -> irm_user_id,
    ARCHITECT -> architect_user_id, PLANNER -> first user with role PLANNER, CISO_BISO -> None
    (mock). Step 1 is Pending with activated_at = clock.now(), the rest Waiting. Id from
    ``next_id(db, ApprovalRequest.id, "APR-")``. Writes an audit event (actor_type from
    created_source) and notifies the first approver via ``notify.deliver`` (in-app + mock email +
    Teams card from services/cards/approval_request.json, or ocet_approval.json for type OCET).
    Raises Conflict (409) if a Pending request of the same type+transition+gate+subject exists.
    ``approvers`` ({step: user_id}) overrides the default approver per step (validated against the
    step role, 422). A step whose approver is the requester is refused (409) unless DEMO_MODE
    (single IRM): then it is allowed and audited as self-approval. ``skip_email_for`` lists emails
    already addressed by a draft being sent (they get the in-app notice only).
    Does not commit.
    """
    config = db.get(ApprovalChainConfig, type)
    if config is None or not config.steps:
        raise BadRequest(f"No approval chain is configured for type {type}")
    db.flush()
    existing = db.scalars(
        select(ApprovalRequest).where(
            ApprovalRequest.type == type,
            ApprovalRequest.transition_id == transition.id,
            ApprovalRequest.status == "Pending",
        )
    ).all()
    if any(r.gate == gate and r.subject_id == subject_id for r in existing):
        raise Conflict(
            "An approval request is already pending",
            [f"A pending {TYPE_LABELS.get(type, type)} request already exists for this subject"],
        )

    chosen = validate_approvers(db, type, approvers)
    now = clock.now()
    steps = []
    for i, cfg in enumerate(sorted(config.steps, key=lambda s: s["step"])):
        approver_id = chosen.get(int(cfg["step"])) or default_approver(db, transition, cfg["role"])
        if (
            approver_id
            and created_by is not None
            and created_source == "Human"
            and approver_id == created_by.id
            and not get_settings().demo_mode
        ):
            raise Conflict(
                "The requester cannot approve their own request",
                [f"Step {cfg['step']} ({cfg.get('label', '')}) would be approved by the requester"],
            )
        steps.append(
            ApprovalStep(
                step=int(cfg["step"]),
                role=cfg["role"],
                label=cfg.get("label", ""),
                approver_user_id=approver_id,
                status="Pending" if i == 0 else "Waiting",
                activated_at=now if i == 0 else None,
            )
        )
    request = ApprovalRequest(
        id=next_id(db, ApprovalRequest.id, "APR-"),
        type=type,
        transition_id=transition.id,
        gate=gate,
        subject_id=subject_id,
        subject_label=subject_label,
        status="Pending",
        created_by=created_by.id if created_by else None,
        created_source=created_source,
        steps=steps,
    )
    db.add(request)
    db.flush()
    audit.record(
        db,
        actor=created_by if created_source == "Human" else None,
        actor_type=_actor_type(created_source),
        entity="ApprovalRequest",
        entity_id=request.id,
        action="created",
        transition_id=transition.id,
        after={**_snap(request), "type": type, "gate": gate, "subject_id": subject_id},
        note=f"{TYPE_LABELS.get(type, type)} requested"
        + (f" (approvers chosen: {chosen})" if chosen else ""),
    )
    _notify_step(db, request, steps[0], transition, skip_email_for)
    return request


def approve_step(
    db: Session, *, request: ApprovalRequest, step: int, user: User, comment: str | None
) -> ApprovalRequest:
    """Approve ``step``. 409 if the request is not Pending or ``step`` is not the current Pending
    step (sequential, BR-041). 403 unless the user is the step's approver, or has the step's role,
    or (CISO_BISO mock step, demo mode) has role IRM. Marks the step Approved, then activates the
    next step and notifies its approver; if it was the last step the request becomes Approved
    (decided_at set), the requester is notified and the completion hook for ``type`` runs
    (EXCEPTION -> exception Approved; AtD/AtO -> none; OCET/SUPPORT_MODEL -> registered hooks).
    Audits every change. Does not commit.
    """
    row = _check_can_act(db, request, step, user)
    transition = db.get(Transition, request.transition_id)
    if transition is None:
        raise NotFound(f"Transition {request.transition_id} not found")
    before = _snap(request)
    now = clock.now()
    mock = is_mock_step(row)
    row.status = "Approved"
    row.decided_at = now
    row.decided_by = user.id
    row.comment = (comment or "").strip() or None
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="ApprovalStep",
        entity_id=f"{request.id}/{row.step}",
        action="step_approved",
        transition_id=request.transition_id,
        before={"status": "Pending"},
        after={"status": "Approved", "comment": row.comment},
        note=f"{row.label} approved"
        + (" as CISO/BISO (mock)" if mock else "")
        + (
            " - self-approved: the requester is the approver (demo mode)"
            if user.id == request.created_by
            else ""
        ),
    )
    following = next(
        (s for s in request.steps if s.step > row.step and s.status == "Waiting"), None
    )
    if following is not None:
        following.status = "Pending"
        following.activated_at = now
        db.flush()
        audit.record(
            db,
            actor=user,
            actor_type="Human",
            entity="ApprovalRequest",
            entity_id=request.id,
            action="step_activated",
            transition_id=request.transition_id,
            before=before,
            after=_snap(request),
            note=f"Step {following.step} ({following.label}) is now pending",
        )
        _notify_step(db, request, following, transition)
        if request.type == "EXCEPTION":
            _sync_exception_status(db, request, following)
    else:
        request.status = "Approved"
        request.decided_at = now
        db.flush()
        audit.record(
            db,
            actor=user,
            actor_type="Human",
            entity="ApprovalRequest",
            entity_id=request.id,
            action="approved",
            transition_id=request.transition_id,
            before=before,
            after=_snap(request),
            note=f"{TYPE_LABELS.get(request.type, request.type)} approved",
        )
        _notify_requester(db, request, transition, "approved", user)
        _run_hooks(db, request)
    return request


def reject_step(
    db: Session, *, request: ApprovalRequest, step: int, user: User, comment: str
) -> ApprovalRequest:
    """Reject ``step`` (same permission/sequence rules as approve_step; comment required, 422 if
    blank). The whole request becomes Rejected, remaining steps Cancelled, the requester
    (created_by) is notified, and the completion hook runs with the Rejected request
    (EXCEPTION -> exception Rejected). Audited. Does not commit.
    """
    if not comment or not comment.strip():
        raise BadRequest(
            "A comment is required to reject", ["Add a comment explaining the rejection"]
        )
    row = _check_can_act(db, request, step, user)
    transition = db.get(Transition, request.transition_id)
    if transition is None:
        raise NotFound(f"Transition {request.transition_id} not found")
    before = _snap(request)
    now = clock.now()
    row.status = "Rejected"
    row.decided_at = now
    row.decided_by = user.id
    row.comment = comment.strip()
    for other in request.steps:
        if other is not row and other.status in ("Waiting", "Pending"):
            other.status = "Cancelled"
    request.status = "Rejected"
    request.decided_at = now
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type="Human",
        entity="ApprovalRequest",
        entity_id=request.id,
        action="rejected",
        transition_id=request.transition_id,
        before=before,
        after={**_snap(request), "comment": row.comment},
        note=f"{row.label} rejected: {row.comment}",
    )
    _notify_requester(db, request, transition, "rejected", user)
    _run_hooks(db, request)
    return request


def cancel_request(
    db: Session, *, request: ApprovalRequest, user: User | None, note: str
) -> ApprovalRequest:
    """Cancel a Pending request (e.g. superseded OCET version): status Cancelled, Waiting/Pending
    steps Cancelled, audited with ``note``. 409 if already finished. Does not commit.
    """
    if request.status != "Pending":
        raise Conflict(
            f"Request {request.id} is {request.status}",
            [f"The request is already {request.status}"],
        )
    before = _snap(request)
    for row in request.steps:
        if row.status in ("Waiting", "Pending"):
            row.status = "Cancelled"
    request.status = "Cancelled"
    request.decided_at = clock.now()
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type="Human" if user else "System",
        entity="ApprovalRequest",
        entity_id=request.id,
        action="cancelled",
        transition_id=request.transition_id,
        before=before,
        after=_snap(request),
        note=note,
    )
    return request


def register_completion_hook(type: str, fn: CompletionHook) -> None:
    """Register ``fn(db, request)`` called when a request of ``type`` becomes Approved or Rejected
    (inspect ``request.status``). Used by M6 (OCET) and M7 (SUPPORT_MODEL). Hooks run in the same
    transaction.
    """
    hooks = _HOOKS.setdefault(type, [])
    if fn not in hooks:
        hooks.append(fn)


def register_card_data(type: str, fn: CardDataProvider) -> None:
    """Optional: ``fn(db, request)`` returns extra Adaptive Card data for ``type`` (e.g. the OCET
    card's version / total_5y / currency / variance_text / top_categories)."""
    _CARD_DATA[type] = fn


def _exception_record(db: Session, request: ApprovalRequest) -> ExceptionRecord | None:
    record = db.get(ExceptionRecord, request.subject_id) if request.subject_id else None
    if record is None:
        record = db.scalars(
            select(ExceptionRecord).where(ExceptionRecord.approval_request_id == request.id)
        ).first()
    return record


def _sync_exception_status(db: Session, request: ApprovalRequest, step: ApprovalStep) -> None:
    """The exception follows the current step: "Pending IRM" -> "Pending CISO/BISO" (workflow rule)."""
    record = _exception_record(db, request)
    if record is None:
        return
    label = pending_status_label(step)
    if record.status == label:
        return
    before = record.status
    record.status = label[:24]
    audit.record(
        db,
        actor=None,
        actor_type="Workflow rule",
        entity="ExceptionRecord",
        entity_id=record.ref,
        action="status_changed",
        transition_id=record.transition_id,
        before={"status": before},
        after={"status": record.status},
        note=f"Approval chain {request.id}: step {step.step} ({step.label}) is now pending",
    )


def _exception_completed(db: Session, request: ApprovalRequest) -> None:
    """EXCEPTION chain finished: the exception follows the request (workflow rule)."""
    record = db.get(ExceptionRecord, request.subject_id) if request.subject_id else None
    if record is None:
        record = db.scalars(
            select(ExceptionRecord).where(ExceptionRecord.approval_request_id == request.id)
        ).first()
    if record is None:
        return
    before = record.status
    record.status = "Approved" if request.status == "Approved" else "Rejected"
    audit.record(
        db,
        actor=None,
        actor_type="Workflow rule",
        entity="ExceptionRecord",
        entity_id=record.ref,
        action="status_changed",
        transition_id=record.transition_id,
        before={"status": before},
        after={"status": record.status},
        note=f"Approval chain {request.id} {request.status.lower()}",
    )


register_completion_hook("EXCEPTION", _exception_completed)
