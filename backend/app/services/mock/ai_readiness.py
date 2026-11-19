"""Mock AIService.readiness_narrative + recommend_actions (M5, FR-050, spec 10.1). Deterministic.

Both functions only produce text / proposals from facts computed by the rules; nothing is executed
(BR-050). The readiness check assembles the inputs (``domain/readiness_check.py``).

``readiness_narrative`` context keys: ``name``, ``verdict``, ``gate_short``, ``blockers`` (list of
``{"item_id", "title"}`` ordered by priority), ``open_conditions`` (list of ``{"id", "item_id"}``),
``first_action`` (label or None), optional ``failed_evals`` (int).

``recommend_actions`` takes one mapping per blocker: ``item_id``, ``title``, ``lens``, ``status``,
``owner_user_id``, ``owner_name``, ``linked_module``, ``transition_id``, ``is_eval``, ``metric``,
``target_text``, ``exception_ref`` (+ ``exception_approver_name`` / ``exception_approver_role`` = the short role label, of
the approver it waits for) and ``noncompliant``. A mapping with
``ready_for_approval=True`` (plus ``gate``, ``transition_id``) yields the ``request_approval`` proposal.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.mock._common import log_mock, simulate_latency

TOP_BLOCKERS = 3
_TITLE_LENGTH = 48


def _short(title: str, length: int = _TITLE_LENGTH) -> str:
    title = " ".join(str(title).split())
    return title if len(title) <= length else title[: length - 1].rstrip() + "..."


def readiness_narrative(ctx: Mapping[str, Any]) -> str:
    """ "{name} is {verdict_lower} for {gate_short}. {n_block} item(s) block approval: {top3}.
    {conditions_sentence} Recommended next step: {first_action}." (spec 10.1)"""
    simulate_latency()
    name = str(ctx.get("name", "This transition"))
    verdict = str(ctx.get("verdict", "Not ready"))
    gate_short = str(ctx.get("gate_short", ""))
    blockers: Sequence[Mapping[str, Any]] = ctx.get("blockers") or []
    conditions: Sequence[Mapping[str, Any]] = ctx.get("open_conditions") or []
    first_action = ctx.get("first_action")

    n_block = len(blockers)
    parts = [f"{name} is {verdict.lower()} for {gate_short}."]
    if n_block:
        top = "; ".join(
            f"{b['item_id']} {_short(b.get('title', ''))}".strip()
            for b in list(blockers)[:TOP_BLOCKERS]
        )
        more = f" (+{n_block - TOP_BLOCKERS} more)" if n_block > TOP_BLOCKERS else ""
        noun = "item blocks" if n_block == 1 else "items block"
        parts.append(f"{n_block} {noun} approval: {top}{more}.")
    else:
        parts.append("No items block approval.")
    if conditions:
        refs = ", ".join(
            f"{c['id']} on {c['item_id']}" if c.get("item_id") else str(c["id"])
            for c in list(conditions)[:TOP_BLOCKERS]
        )
        noun = "condition is" if len(conditions) == 1 else "conditions are"
        parts.append(f"{len(conditions)} open {noun} due by this gate ({refs}).")
    else:
        parts.append("There are no open conditions due by this gate.")
    if first_action:
        # A label can end with an item title that is a question ("... the application?").
        stop = "" if str(first_action).endswith((".", "?", "!")) else "."
        parts.append(f"Recommended next step: {first_action}{stop}")
    log_mock("AIService", "readiness_narrative", name=name, verdict=verdict, blockers=n_block)
    return " ".join(parts)


def _proposal(
    kind: str, key_item: str, label: str, item_ids: list[str], href: str | None = None
) -> dict[str, Any]:
    return {
        "key": f"{kind}:{key_item}",
        "label": label,
        "kind": kind,
        "item_ids": item_ids,
        "href": href,
    }


def _ask_to_approve_exception(gap: Mapping[str, Any], item_id: str) -> str:
    """ "Ask Fatima Khan (IRM) to approve exception EX-01" (the approver the exception waits for)."""
    name = gap.get("exception_approver_name")
    role = gap.get("exception_approver_role")
    who = f"{name} ({role})" if name and role else "the approver"
    return f"Ask {who} to approve exception {gap['exception_ref']} for {item_id}"


def _one(gap: Mapping[str, Any]) -> dict[str, Any]:
    item_id = str(gap.get("item_id", ""))
    title = _short(str(gap.get("title", "")))
    tid = gap.get("transition_id")
    module = gap.get("linked_module")
    owner = gap.get("owner_name")
    if gap.get("ready_for_approval"):
        gate = gap.get("gate", "")
        return _proposal("request_approval", str(gate), "Request approval", [], None)
    if gap.get("is_eval"):
        target = gap.get("target_text", "")
        metric = gap.get("metric") or title
        return _proposal(
            "create_action", item_id, f"Create action to bring {metric} to {target}", [item_id]
        )
    if module == "OCET":
        return _proposal(
            "open_ocet",
            item_id,
            f"Open OCET to unblock {item_id}",
            [item_id],
            f"/transitions/{tid}/ocet" if tid else None,
        )
    if module == "SUPPORT_MODEL":
        return _proposal(
            "create_support_model",
            item_id,
            f"Create the support model for {item_id}",
            [item_id],
            f"/transitions/{tid}/support-model" if tid else None,
        )
    if gap.get("noncompliant") and not gap.get("exception_ref"):
        return _proposal(
            "request_exception",
            item_id,
            f"Request an exception for {item_id} {title}",
            [item_id],
        )
    if gap.get("owner_user_id"):
        if gap.get("exception_ref"):
            label = _ask_to_approve_exception(gap, item_id)
        else:
            # "Draft a chaser to Daniel Brooks for S02-033 ...": the owner is the one being chased.
            to_owner = f" to {owner}" if owner else ""
            label = f"Draft a chaser{to_owner} for {item_id} {title}"
        return _proposal("draft_chaser", item_id, label, [item_id])
    return _proposal("create_action", item_id, f"Create an action for {item_id} {title}", [item_id])


def recommend_actions(gaps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One proposal per blocker (input order kept; the caller orders blockers by priority)."""
    simulate_latency()
    proposals = [_one(g) for g in gaps]
    log_mock("AIService", "recommend_actions", gaps=len(gaps), proposals=len(proposals))
    return proposals
