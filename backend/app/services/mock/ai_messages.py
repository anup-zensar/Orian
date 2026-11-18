"""Mock AIService.draft_message (M5, FR-071, spec 10.1 chaser template). Deterministic.

``ctx`` keys (all optional unless stated; missing values degrade gracefully):

* ``transition_name`` / ``transition_id`` / ``gate_short`` / ``days`` (days to the decision, may be
  negative or None) / ``or_focal_name`` / ``recipient_name``
* ``items``: list of ``{"id", "title", "due_gate_short"?, "owner_name"?, "deep_link"?}`` (Chaser,
  Reminder, Input request)
* ``deep_link``: overrides the default link (otherwise ``APP_BASE_URL`` + the standard route)
* Approval request: ``gate``, ``verdict``, ``approver_role``, ``summary``; ``ready`` (R4: the
  draft is for the OR focal and Send starts the chain) with ``subject``
* Reminder-engine variants (BR-060): Chaser with ``days_overdue``/``action_title`` (R2) or
  ``escalation`` + ``approver_name`` + ``days_pending`` (R3); Reminder with ``pending_step``
  (R3), ``monitoring`` (R6) or ``support_model`` (R7) + ``subject``
* Leadership update: ``scope`` (title) and ``text`` (plain lines, blank line = new paragraph)

The text is only a draft: nothing is sent until a human clicks Send (BR-050).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.config import get_settings
from app.domain.html_sanitize import escape_text as esc
from app.services.interfaces import DraftText
from app.services.mock._common import log_mock, simulate_latency

KINDS = ("chaser", "reminder", "input request", "approval request", "leadership update")


def _s(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _base() -> str:
    return get_settings().app_base_url.rstrip("/")


def _when(ctx: Mapping[str, Any]) -> str:
    """``AtD in 21 days`` / ``AtD overdue by 2 days`` / ``AtD today`` / ``AtD``."""
    gate = str(ctx.get("gate_short") or "").strip()
    days = ctx.get("days")
    if days is None:
        return gate
    days = int(days)
    if days < 0:
        return f"{gate} overdue by {_s(-days, 'day')}".strip()
    if days == 0:
        return f"{gate} today".strip()
    return f"{gate} in {_s(days, 'day')}".strip()


def _item_link(ctx: Mapping[str, Any], item: Mapping[str, Any]) -> str:
    if item.get("deep_link"):
        return str(item["deep_link"])
    return (
        f"{_base()}/transitions/{ctx.get('transition_id', '')}/assessment?item={item.get('id', '')}"
    )


def _items(ctx: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [i for i in (ctx.get("items") or []) if isinstance(i, Mapping)]


def _greeting(ctx: Mapping[str, Any]) -> str:
    name = str(ctx.get("recipient_name") or "").strip()
    return f"Hi {esc(name)}," if name else "Hello,"


def _sign_off(ctx: Mapping[str, Any]) -> str:
    focal = str(ctx.get("or_focal_name") or "the OR focal").strip()
    return f"<p>Thank you,<br>Orion, on behalf of {esc(focal)}</p>"


def _item_list(ctx: Mapping[str, Any]) -> str:
    rows = []
    for item in _items(ctx):
        due = str(item.get("due_gate_short") or ctx.get("gate_short") or "").strip()
        owner = str(item.get("owner_name") or "").strip()
        extra = ", ".join(x for x in (f"due at {due}" if due else "", owner) if x)
        rows.append(
            f'<li><a href="{esc(_item_link(ctx, item))}">{esc(item.get("id", ""))}</a> '
            f"{esc(item.get('title', ''))}" + (f" ({esc(extra)})" if extra else "") + "</li>"
        )
    return f"<ul>{''.join(rows)}</ul>" if rows else ""


def _item_title(ctx: Mapping[str, Any]) -> str:
    items = _items(ctx)
    if not items:
        return "open items"
    first = str(items[0].get("title", "")).strip() or str(items[0].get("id", ""))
    return first if len(items) == 1 else f"{first} and {_s(len(items) - 1, 'other item')}"


def _link_para(ctx: Mapping[str, Any], label: str = "Open in Orion") -> str:
    return f'<p><a href="{esc(ctx.get("deep_link") or _base())}">{esc(label)}</a></p>'


def _overdue_action(ctx: Mapping[str, Any]) -> DraftText:
    transition = str(ctx.get("transition_name", ""))
    title = str(ctx.get("action_title") or "an action")
    days = int(ctx.get("days_overdue") or 0)
    body = (
        f"<p>{_greeting(ctx)}</p>"
        f"<p>The action <strong>{esc(title)}</strong> for {esc(transition)} was due "
        f"{esc(str(ctx.get('due_date') or ''))} and is now overdue by {_s(days, 'day')}. "
        f"Could you please update it or let us know what is blocking you?</p>"
        + _link_para(ctx)
        + _sign_off(ctx)
    )
    return {
        "subject": f"Overdue action: {title} for {transition} ({_s(days, 'day')} overdue)",
        "body_html": body,
    }


def _escalation(ctx: Mapping[str, Any]) -> DraftText:
    transition = str(ctx.get("transition_name", ""))
    approver = str(ctx.get("approver_name") or "The approver")
    gate = str(ctx.get("gate_short") or "the gate")
    days = int(ctx.get("days_pending") or 0)
    body = (
        f"<p>{_greeting(ctx)}</p>"
        f"<p>{esc(approver)} has not yet decided the {esc(gate)} approval for "
        f"{esc(transition)}; it has been pending for {_s(days, 'day')}. "
        f"You may want to follow up with them directly.</p>" + _link_para(ctx) + _sign_off(ctx)
    )
    return {
        "subject": f"Escalation: {gate} approval for {transition} pending {_s(days, 'day')}",
        "body_html": body,
    }


def _chaser(ctx: Mapping[str, Any]) -> DraftText:
    if ctx.get("escalation"):
        return _escalation(ctx)
    if ctx.get("days_overdue") is not None:
        return _overdue_action(ctx)
    transition = str(ctx.get("transition_name", ""))
    when = _when(ctx)
    subject = f"Action needed: {_item_title(ctx)} for {transition}"
    if when:
        subject += f" ({when})"
    n = len(_items(ctx))
    intro = (
        f"<p>{_greeting(ctx)}</p>"
        f"<p>{esc(transition)} is heading to {esc(when or 'its next gate')}. "
        f"Could you please update {'this item' if n == 1 else 'these items'} "
        f"or let us know what is blocking you?</p>"
    )
    link = esc(ctx.get("deep_link") or _item_link(ctx, _items(ctx)[0] if _items(ctx) else {}))
    body = intro + _item_list(ctx) + f'<p><a href="{link}">Open in Orion</a></p>' + _sign_off(ctx)
    return {"subject": subject, "body_html": body}


def _simple_reminder(ctx: Mapping[str, Any], subject: str, text: str) -> DraftText:
    body = (
        f"<p>{_greeting(ctx)}</p><p>{text}</p>" + _item_list(ctx) + _link_para(ctx) + _sign_off(ctx)
    )
    return {"subject": subject, "body_html": body}


def _reminder(ctx: Mapping[str, Any]) -> DraftText:
    transition = str(ctx.get("transition_name", ""))
    gate_short = str(ctx.get("gate_short") or "the gate")
    if ctx.get("pending_step"):
        days = int(ctx.get("days_pending") or 0)
        return _simple_reminder(
            ctx,
            f"Reminder: {gate_short} approval for {transition} is waiting for you",
            f"Your approval of {esc(gate_short)} for {esc(transition)} has been pending for "
            f"{_s(days, 'day')}. Please review and decide in Orion.",
        )
    if ctx.get("monitoring"):
        return _simple_reminder(
            ctx,
            f"Monitoring requirements for {transition}",
            f"{esc(transition)} is in the design stage. Please capture the monitoring "
            f"requirements below with the team.",
        )
    if ctx.get("support_model"):
        return _simple_reminder(
            ctx,
            str(ctx.get("subject") or "Create support model now?"),
            f"The support-model evidence for {esc(transition)} has been accepted. "
            f"Orion can now prepare the support model.",
        )
    n = len(_items(ctx))
    when = _when(ctx)
    subject = f"Reminder: {_s(n, 'open item')} for {transition}" + (f" ({when})" if when else "")
    body = (
        f"<p>{_greeting(ctx)}</p>"
        f"<p>A friendly reminder that {_s(n, 'item')} for {esc(transition)} "
        f"{'is' if n == 1 else 'are'} still open.</p>" + _item_list(ctx) + _sign_off(ctx)
    )
    return {"subject": subject, "body_html": body}


def _input_request(ctx: Mapping[str, Any]) -> DraftText:
    transition = str(ctx.get("transition_name", ""))
    n = len(_items(ctx))
    subject = f"Input needed: {_s(n, 'input')} for {transition}"
    body = (
        f"<p>{_greeting(ctx)}</p>"
        f"<p>To complete the estimate for {esc(transition)} we still need your input on:</p>"
        + _item_list(ctx)
        + "<p>Please reply with the figures or add them directly in Orion.</p>"
        + _sign_off(ctx)
    )
    return {"subject": subject, "body_html": body}


def _ready_for_gate(ctx: Mapping[str, Any], transition: str, gate: str) -> DraftText:
    role = str(ctx.get("approver_role") or "the first approver")
    subject = str(ctx.get("subject") or f"Ready for {gate} - request {role} approval")
    body = (
        f"<p>{_greeting(ctx)}</p>"
        f"<p>{esc(transition)} has no open items left for {esc(gate)}. "
        f"Sending this starts the approval chain with {esc(role)}.</p>"
        + _link_para(ctx, "Review readiness in Orion")
        + _sign_off(ctx)
    )
    return {"subject": subject, "body_html": body}


def _approval_request(ctx: Mapping[str, Any]) -> DraftText:
    transition = str(ctx.get("transition_name", ""))
    gate = str(ctx.get("gate_short") or ctx.get("gate") or "gate")
    if ctx.get("ready"):
        return _ready_for_gate(ctx, transition, gate)
    link = ctx.get("deep_link") or f"{_base()}/transitions/{ctx.get('transition_id', '')}/gates"
    verdict = str(ctx.get("verdict") or "").strip()
    role = str(ctx.get("approver_role") or "").strip()
    summary = str(ctx.get("summary") or "").strip()
    body = (
        f"<p>{_greeting(ctx)}</p>"
        f"<p>{esc(transition)} is ready for your approval at {esc(gate)}"
        + (f" (readiness: {esc(verdict)})" if verdict else "")
        + ".</p>"
        + (f"<p>{esc(summary)}</p>" if summary else "")
        + (f"<p>First approver: {esc(role)}.</p>" if role else "")
        + f'<p><a href="{esc(link)}">Review and approve in Orion</a></p>'
        + _sign_off(ctx)
    )
    return {"subject": f"Approval request: {gate} for {transition}", "body_html": body}


def _leadership_update(ctx: Mapping[str, Any]) -> DraftText:
    scope = str(ctx.get("scope") or ctx.get("transition_name") or "all transitions")
    paragraphs = [p.strip() for p in str(ctx.get("text") or "").split("\n\n") if p.strip()]
    body = (
        f"<p>{_greeting(ctx)}</p>"
        + "".join(f"<p>{esc(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)
        + _sign_off(ctx)
    )
    return {"subject": f"Leadership update: {scope}", "body_html": body}


_BUILDERS = {
    "chaser": _chaser,
    "reminder": _reminder,
    "input request": _input_request,
    "approval request": _approval_request,
    "leadership update": _leadership_update,
}


def draft_message(kind: str, ctx: Mapping[str, Any]) -> DraftText:
    """Subject + HTML body for a draft of ``kind`` (case-insensitive: Chaser, Reminder, Input
    request, Approval request, Leadership update)."""
    simulate_latency()
    key = " ".join(kind.replace("_", " ").replace("-", " ").lower().split())
    builder = _BUILDERS.get(key)
    if builder is None:
        raise ValueError(f"Unknown draft kind {kind!r}; expected one of {', '.join(KINDS)}")
    log_mock("AI", "draft_message", kind=key, transition=ctx.get("transition_id", ""))
    return builder(ctx)
