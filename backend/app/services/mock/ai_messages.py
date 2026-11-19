"""Mock AIService.draft_message (M5, FR-071, spec 10.1 chaser template). Deterministic.

``ctx`` keys (all optional unless stated; missing values degrade gracefully):

* ``transition_name`` / ``transition_id`` / ``gate_short`` / ``days`` (days to the decision, may be
  negative or None) / ``or_focal_name`` / ``recipient_name``
* ``items``: list of ``{"id", "title", "due_gate_short"?, "owner_name"?, "deep_link"?}`` (Chaser,
  Reminder, Input request)
* ``deep_link``: overrides the default link (otherwise ``APP_BASE_URL`` + the standard route)
* Approval request: ``gate``, ``verdict``, ``approver_role``, ``summary`` (rule R4 uses this
  same text, addressed to the first approver, with its own subject)
* Reminder-engine variants (BR-060): Chaser with ``days_overdue``/``action_title`` (R2) or
  ``escalation`` + ``approver_name`` + ``days_pending`` (R3); Reminder with ``pending_step``
  (R3), ``monitoring`` (R6) or ``support_model`` (R7)
* Leadership update: ``scope`` (title) and ``text`` (plain lines, blank line = new paragraph)
* ``templates``: {key: TemplateCfg}, the message templates saved under Admin > Messages. Without it
  the code defaults (``domain/cfg_defaults.py``) are used.

Every message is a template: this module only works out the placeholder values (names, counts,
links, the item list) and fills the template. The text is only a draft: nothing is sent until a
human clicks Send (BR-050).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.config import get_settings
from app.domain import cfg, cfg_defaults
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


def _render(key: str, ctx: Mapping[str, Any], values: Mapping[str, Any]) -> DraftText:
    """Fill the template ``key`` (the saved one from ``ctx["templates"]`` when it is switched on,
    else the code default) with ``values`` plus the placeholders every message has."""
    saved = (ctx.get("templates") or {}).get(key)
    if saved is not None and saved.enabled:
        subject, body = saved.subject, saved.body
    else:
        _name, subject, body, _source = cfg_defaults.DEFAULT_TEMPLATES[key]
    common = {
        "recipient_name": ctx.get("recipient_name") or "",
        "transition_name": ctx.get("transition_name") or "",
        "gate_short": ctx.get("gate_short") or "",
        "days": ctx.get("days") if ctx.get("days") is not None else "",
        "or_focal_name": ctx.get("or_focal_name") or "",
        "orion_name": "Orion",
        "greeting": _greeting(ctx),
        "sign_off": _sign_off(ctx),
        "deep_link": ctx.get("deep_link") or _base(),
        "item_list": _item_list(ctx),
    }
    merged = {**common, **values}
    html_names = [n for n, (_desc, is_html) in cfg_defaults.PLACEHOLDERS.items() if is_html]
    return {
        # the subject is plain text (nothing escaped); the body is HTML (only plain values escaped)
        "subject": cfg.render(subject, merged, html_placeholders=list(merged)),
        "body_html": cfg.render(body, merged, html_placeholders=html_names),
    }


def _overdue_action(ctx: Mapping[str, Any]) -> DraftText:
    days = int(ctx.get("days_overdue") or 0)
    return _render(
        "overdue_action",
        ctx,
        {
            "action_title": str(ctx.get("action_title") or "an action"),
            "due_date": str(ctx.get("due_date") or ""),
            "days_overdue_text": _s(days, "day"),
        },
    )


def _escalation(ctx: Mapping[str, Any]) -> DraftText:
    days = int(ctx.get("days_pending") or 0)
    return _render(
        "escalation",
        ctx,
        {
            "approver_name": str(ctx.get("approver_name") or "The approver"),
            "gate_short": str(ctx.get("gate_short") or "the gate"),
            "days_pending_text": _s(days, "day"),
        },
    )


def _chaser(ctx: Mapping[str, Any]) -> DraftText:
    if ctx.get("escalation"):
        return _escalation(ctx)
    if ctx.get("days_overdue") is not None:
        return _overdue_action(ctx)
    when = _when(ctx)
    items = _items(ctx)
    return _render(
        "chaser",
        ctx,
        {
            "item_title": _item_title(ctx),
            "when_suffix": f" ({when})" if when else "",
            "when_or_next_gate": when or "its next gate",
            "item_phrase": "this item" if len(items) == 1 else "these items",
            "deep_link": ctx.get("deep_link") or _item_link(ctx, items[0] if items else {}),
        },
    )


def _reminder(ctx: Mapping[str, Any]) -> DraftText:
    if ctx.get("pending_step"):
        days = int(ctx.get("days_pending") or 0)
        return _render(
            "pending_approval",
            ctx,
            {
                "gate_short": str(ctx.get("gate_short") or "the gate"),
                "days_pending_text": _s(days, "day"),
            },
        )
    if ctx.get("monitoring"):
        return _render("monitoring_request", ctx, {})
    if ctx.get("support_model"):
        return _render("support_model_prompt", ctx, {})
    n = len(_items(ctx))
    when = _when(ctx)
    return _render(
        "reminder",
        ctx,
        {
            "open_item_count_text": _s(n, "open item"),
            "item_count_text": _s(n, "item"),
            "when_suffix": f" ({when})" if when else "",
            "is_are": "is" if n == 1 else "are",
        },
    )


def _input_request(ctx: Mapping[str, Any]) -> DraftText:
    return _render("input_request", ctx, {"input_count_text": _s(len(_items(ctx)), "input")})


def _approval_request(ctx: Mapping[str, Any]) -> DraftText:
    gate = str(ctx.get("gate_short") or ctx.get("gate") or "gate")
    link = ctx.get("deep_link") or f"{_base()}/transitions/{ctx.get('transition_id', '')}/gates"
    verdict = str(ctx.get("verdict") or "").strip()
    role = str(ctx.get("approver_role") or "").strip()
    summary = str(ctx.get("summary") or "").strip()
    return _render(
        "approval_request",
        ctx,
        {
            "gate_short": gate,
            "deep_link": link,
            "verdict": verdict,
            "approver_role": role,
            "verdict_suffix": f" (readiness: {esc(verdict)})" if verdict else "",
            "summary_html": f"<p>{esc(summary)}</p>" if summary else "",
            "approver_line": f"<p>First approver: {esc(role)}.</p>" if role else "",
        },
    )


def _leadership_update(ctx: Mapping[str, Any]) -> DraftText:
    scope = str(ctx.get("scope") or ctx.get("transition_name") or "all transitions")
    paragraphs = [p.strip() for p in str(ctx.get("text") or "").split("\n\n") if p.strip()]
    return _render(
        "leadership_update",
        ctx,
        {
            "scope": scope,
            "paragraphs": "".join(f"<p>{esc(p).replace(chr(10), '<br>')}</p>" for p in paragraphs),
        },
    )


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
