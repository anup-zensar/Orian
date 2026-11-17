"""Mock AI service (spec 10.1).

Every method exists so the class satisfies ``AIService``; each is implemented together with its
caller in a later milestone (PLAN.md):

* ``insights``                 - M2
* ``recommend_applicability``  - M3
* ``readiness_narrative``, ``recommend_actions``, ``draft_message`` - M5
* ``explain_ocet_change``      - M6
* ``chat``, ``leadership_update`` - M8
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.services.interfaces import DraftText
from app.services.mock._common import log_mock, simulate_latency

MAX_INSIGHTS = 5
TITLE_LENGTH = 60
_LABEL_CUTS = (" - ", " (", ": ")
_MIN_LABEL = 15


def _short(title: str, length: int = TITLE_LENGTH) -> str:
    """A short label for an item title: the text before " - ", " (" or ": " when that leaves a
    meaningful label, else the title cut at a word boundary around ``length`` characters."""
    title = " ".join(str(title).split())
    for cut in _LABEL_CUTS:
        head = title.split(cut, 1)[0].rstrip()
        if cut in title and len(head) >= _MIN_LABEL:
            title = head
            break
    if len(title) <= length:
        return title
    cut_at = title.rfind(" ", 0, length + 1)
    if cut_at < _MIN_LABEL:
        cut_at = length
    return title[:cut_at].rstrip(" ,;:-/") + "…"


def _s(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _when(f: Mapping[str, Any]) -> str | None:
    """``AtD in 21 days`` / ``AtD overdue by 2 days`` / None when there is no decision date."""
    days = f.get("days")
    if days is None:
        return None
    gate = f["gate_short"]
    if days < 0:
        return f"{gate} overdue by {_s(-days, 'day')}"
    if days == 0:
        return f"{gate} today"
    return f"{gate} in {_s(days, 'day')}"


def _risk_parts(f: Mapping[str, Any]) -> str:
    parts = []
    if f["critical_gaps"] > 0:
        parts.append(_s(f["critical_gaps"], "critical gap"))
    if not f.get("launched", True):
        parts.append("assessment not launched yet")
    elif f["lowest_lens_pct"] < 70:
        parts.append(f"{f['lowest_lens']} readiness {f['lowest_lens_pct']}%")
    when = _when(f)
    if when:
        parts.append(when)
    return ", ".join(parts) if parts else "needs attention"


def _insight(
    key: str,
    text: str,
    severity: str,
    transition_id: str | None = None,
    actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": key,
        "text": text,
        "severity": severity,
        "transition_id": transition_id,
        "actions": actions or [],
    }


def _link(label: str, href: str) -> dict[str, Any]:
    return {"label": label, "kind": "link", "href": href, "proposal_id": None}


def _dashboard_insights(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in data["critical_transitions"][:3]:
        gaps = f["gaps"]
        first = gaps[0] if gaps else None
        n = f["critical_gaps"]
        what = f"{first['id']} {_short(first['title'])}" if first else "see gaps"
        if first and n > 1:
            what += f", +{n - 1} more"
        when = _when(f)
        lead = f"{f['name']}: {when}, blocked by" if when else f"{f['name']}: blocked by"
        # Real chasers (Orion drafts, the human sends) arrive with M5 / M8: M2 only links to the gap.
        chaser = f"/transitions/{f['id']}/gaps" + (f"?item={first['id']}" if first else "")
        out.append(
            _insight(
                f"{f['id']}:critical-gap",
                f"{lead} {_s(n, 'critical gap')} ({what})."
                + ("" if data["user"].get("role") == "LEADERSHIP" else " Draft a chaser?"),
                "critical",
                f["id"],
                [_link("Open gaps", f"/transitions/{f['id']}/gaps")]
                + (
                    []
                    if data["user"].get("role") == "LEADERSHIP"  # read-only: no drafting
                    else [_link("Draft a chaser", chaser)]
                ),
            )
        )
    approvals = data["approvals_waiting"]
    if approvals:
        first = approvals[0]
        extra = f" (+{len(approvals) - 1} more)" if len(approvals) > 1 else ""
        out.append(
            _insight(
                "approvals:waiting",
                f"{_s(len(approvals), 'approval')} waiting for you: {_short(first['label'])} on "
                f"{first['transition_name']}, waiting {_s(first['waiting_days'], 'day')}{extra}.",
                "warning",
                first["transition_id"],
                [_link("Open approvals", f"/approvals?request={first['request_id']}")],
            )
        )
    overdue = data["overdue_actions"]
    if overdue:
        first = overdue[0]
        href = f"/transitions/{first['transition_id']}/gaps?action={first['id']}"
        out.append(
            _insight(
                "actions:overdue",
                f"{_s(len(overdue), 'overdue action')} in your transitions: {_short(first['title'])} "
                f"({first['transition_name']}, {_s(first['days_overdue'], 'day')} overdue).",
                "warning",
                first["transition_id"],
                [_link("Open action", href)],
            )
        )
    for f in data["low_readiness"][:2]:
        out.append(
            _insight(
                f"{f['id']}:low-readiness",
                f"{f['name']}: {f['lowest_lens']} readiness {f['lowest_lens_pct']}% with "
                f"{_when(f)}",
                "warning",
                f["id"],
                [_link("Open assessment", f"/transitions/{f['id']}/assessment")],
            )
        )
    if not out:
        out.append(_insight("dashboard:on-track", "All your transitions are on track", "success"))
    return out[:MAX_INSIGHTS]


def _control_tower_insights(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    risks = data["top_risks"]
    if not risks:
        return [
            _insight(
                "control-tower:on-track",
                "No red or amber transitions in the current view.",
                "success",
            )
        ]
    out = []
    for f in risks:
        text = f"{f['name']} ({f['portfolio']}) is {f['rag']}: {_risk_parts(f)}."
        if f["blocker_note"]:
            text += f" Blocker: {f['blocker_note']}"
        out.append(
            _insight(
                f"{f['id']}:risk",
                text,
                "critical" if f["rag"] == "Red" else "warning",
                f["id"],
                [
                    _link("Open transition", f"/transitions/{f['id']}"),
                    _link("Open gaps", f"/transitions/{f['id']}/gaps"),
                ],
            )
        )
    top = risks[0]
    gap = top["gaps"][0] if top["gaps"] else None
    blocker = top["blocker_note"] or (
        f"{gap['id']} {_short(gap['title'])}" if gap else "the open gaps"
    )
    when = _when(top)
    out.append(
        _insight(
            "control-tower:leadership-ask",
            f"Suggested ask for the leadership meeting: help unblock {top['name']} ({blocker})"
            + (f" before {when}." if when else "."),
            "info",
            top["id"],
            [_link("Open transition", f"/transitions/{top['id']}")],
        )
    )
    return out


def _transition_insights(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    f = data["transition"]
    tid = f["id"]
    out = []
    when = _when(f)
    if when:
        readiness = (
            f"Overall readiness {f['overall_readiness']}%, status {f['rag']}."
            if data["has_items"]
            else f"Status {f['rag']}."
        )
        out.append(
            _insight(
                f"{tid}:next-decision",
                f"Next decision: {when} ({f['next_decision_date']}). {readiness}",
                "critical" if f["rag"] == "Red" else "info",
                tid,
            )
        )
    if not data["has_items"]:
        out.append(
            _insight(
                f"{tid}:not-launched",
                "The readiness assessment has not been launched yet.",
                "info",
                tid,
                [_link("Open scope", f"/transitions/{tid}/scope")],
            )
        )
        return out
    gaps = f["gaps"][:3]
    if gaps:
        listing = "; ".join(
            f"{g['id']} ({g['severity'] or 'gap'}) {_short(g['title'])}" for g in gaps
        )
        out.append(
            _insight(
                f"{tid}:top-gaps",
                f"Top gaps: {listing}.",
                "critical" if f["critical_gaps"] else "warning",
                tid,
                [_link("Open gaps", f"/transitions/{tid}/gaps")],
            )
        )
    else:
        out.append(_insight(f"{tid}:no-gaps", "No open gaps at the current gate.", "success", tid))
    out.append(
        _insight(
            f"{tid}:lowest-lens",
            f"Lowest lens: {f['lowest_lens']} at {f['lowest_lens_pct']}%.",
            "warning" if f["lowest_lens_pct"] < 70 else "info",
            tid,
            [_link("Open assessment", f"/transitions/{tid}/assessment")],
        )
    )
    if f["blocker_note"]:
        out.append(_insight(f"{tid}:blocker", f"Blocker: {f['blocker_note']}", "warning", tid))
    return out


class MockAIService:
    def readiness_narrative(self, ctx: Mapping[str, Any]) -> str:
        from app.services.mock import ai_readiness  # M5 gates module (own file per area)

        return ai_readiness.readiness_narrative(ctx)

    def recommend_actions(self, gaps: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        from app.services.mock import ai_readiness

        return ai_readiness.recommend_actions(gaps)

    def recommend_applicability(
        self, items: Sequence[Mapping[str, Any]], flavour: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        from app.services.mock import ai_applicability  # M3 scope module

        return ai_applicability.recommend_applicability(items, flavour)

    def draft_message(self, kind: str, ctx: Mapping[str, Any]) -> DraftText:
        from app.services.mock import ai_messages  # M5 drafts module

        return ai_messages.draft_message(kind, ctx)

    def leadership_update(self, scope_data: Mapping[str, Any]) -> str:
        raise NotImplementedError("leadership_update is implemented in M8")

    def explain_ocet_change(self, diff: Mapping[str, Any]) -> str:
        raise NotImplementedError("explain_ocet_change is implemented in M6")

    def chat(self, message: str, context: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("chat is implemented in M8")

    def insights(self, scope_data: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Fixed templates over facts gathered by ``domain.insights`` (deterministic, FR-010/011).

        Read-only: nothing is stored and the buttons are links (BR-050).
        """
        simulate_latency()
        scope = scope_data["scope"]
        log_mock("AIService", "insights", scope=scope, user=scope_data["user"]["id"])
        if scope == "dashboard":
            return _dashboard_insights(scope_data)
        if scope == "control-tower":
            return _control_tower_insights(scope_data)
        return _transition_insights(scope_data)
