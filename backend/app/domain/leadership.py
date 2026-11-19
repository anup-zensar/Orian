"""Leadership updates (FR-080). Orion drafts the text from live data; a permitted human sends it.
NFR-04: generating or storing an update writes no statuses/decisions."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.config import get_settings
from app.domain import audit, cfg
from app.domain.drafts import validate_addresses
from app.domain.html_sanitize import escape_text, sanitize_html
from app.domain.metrics import TransitionMetrics, compute_metrics
from app.errors import ApiError, NotFound
from app.models import (
    Action,
    ApprovalRequest,
    AuditEvent,
    Condition,
    ExceptionRecord,
    GateReview,
    LeadershipUpdate,
    Portfolio,
    Risk,
    Transition,
    User,
)
from app.rules.constants import ACTOR_HUMAN, ACTOR_ORION, GAP_STATUSES, GATE_SHORT
from app.schemas.common import PersonRef
from app.schemas.leadership import LeadershipScope, LeadershipUpdateOut
from app.services.factory import get_ai_service, get_mail_service

RECENT_APPROVAL_DAYS = 90
RECENT_WIN_DAYS = 30
MAX_RISKS = 8
RAG_RANK = {"Red": 0, "Amber": 1, "Green": 2, "Grey": 3}
OPEN_ACTION = ("Open", "In progress")


def _short(text: str, length: int = 70) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def _select_transitions(
    db: Session, scope: LeadershipScope, scope_id: str | None
) -> tuple[list[Transition], str]:
    if scope == "all":
        if scope_id:
            raise ApiError("scope 'all' takes no scope_id", ["Omit scope_id for scope=all"])
        rows = db.scalars(
            select(Transition).where(Transition.status == "Active").order_by(Transition.id)
        ).all()
        return list(rows), "Leadership update - all transitions"
    if not scope_id:
        raise ApiError(
            f"scope '{scope}' needs a scope_id", [f"Give a {scope} id for scope={scope}"]
        )
    if scope == "transition":
        t = db.get(Transition, scope_id)
        if t is None:
            raise NotFound(f"Transition {scope_id} not found")
        return [t], f"Leadership update - {t.name} ({t.id})"
    if db.get(Portfolio, scope_id) is None:
        raise NotFound(f"Portfolio {scope_id} not found")
    rows = db.scalars(
        select(Transition)
        .where(Transition.portfolio == scope_id, Transition.status == "Active")
        .order_by(Transition.id)
    ).all()
    return list(rows), f"Leadership update - {scope_id} portfolio"


def _critical_gaps(m: TransitionMetrics, critical: str) -> list[str]:
    """Open gaps of the severity the admin marked "counts as critical" (cfg.critical_severity)."""
    out = []
    for i in m.items:
        if (
            i.gap_severity == critical
            and i.status in GAP_STATUSES
            and i.applicability == "Applies"
            and not i.covered
        ):
            out.append(
                f"{m.transition.name}: {i.playbook_item_id} {_short(i.title)} is a critical gap"
            )
    return out


def _human_date(iso: str) -> str:
    """ "2026-11-18" -> "18 Nov 2026" (the app's date style)."""
    day = date.fromisoformat(iso)
    return f"{day.day} {day:%b %Y}"


def collect_scope_data(db: Session, scope: LeadershipScope, scope_id: str | None) -> dict[str, Any]:
    """Live data for ``AIService.leadership_update``: keys ``scope``, ``scope_id``, ``title``, ``today``,
    ``transitions`` (id, name, portfolio, current gate, RAG, readiness %, days to decision, verdict),
    ``portfolios`` (per portfolio counts by RAG/gate), ``risks`` (top open risks/blockers incl.
    critical gaps), ``decisions_next_30_days`` (gate decisions due within 30 days of today,
    clock-aware), ``approvals`` (recent AtD/AtO approvals with date and approver - storyline step 10:
    the GCC portfolio update must show the AtD approval and the remaining risks), ``asks`` (open
    conditions, pending exceptions, overdue items), ``wins`` (approvals, closed gaps). NotFound 404
    for an unknown transition id / portfolio name; BadRequest 400 when scope=all with a scope_id, or
    scope!=all without one."""
    today = clock.today()
    critical = cfg.critical_severity(db)
    transitions, title = _select_transitions(db, scope, scope_id)
    metrics = compute_metrics(db, transitions)
    by_id = {m.id: m for m in metrics}
    users = {u.id: u for u in db.scalars(select(User)).all()}
    ids = [t.id for t in transitions]

    verdicts = {
        "Green": "On track",
        "Amber": "Needs attention",
        "Red": "At risk",
        "Grey": "Not launched",
    }
    rows = []
    for m in sorted(metrics, key=lambda x: (RAG_RANK.get(x.rag, 9), x.id)):
        t = m.transition
        rows.append(
            {
                "id": t.id,
                "name": t.name,
                "portfolio": t.portfolio,
                "gate": t.current_gate,
                "gate_short": GATE_SHORT.get(t.current_gate, t.current_gate),
                "rag": m.rag,
                "readiness": m.readiness.overall,
                "days": m.days_to_next_decision,
                "next_decision": t.next_decision_date.isoformat() if t.next_decision_date else None,
                "verdict": verdicts.get(m.rag, m.rag),
                "critical_gaps": m.critical_gaps,
            }
        )

    portfolios = []
    for name in sorted({t.portfolio for t in transitions}):
        group = [m for m in metrics if m.transition.portfolio == name]
        portfolios.append(
            {
                "name": name,
                "count": len(group),
                "rag": dict(Counter(m.rag for m in group)),
                "gates": dict(
                    Counter(GATE_SHORT.get(m.transition.current_gate, "") for m in group)
                ),
            }
        )

    risks: list[dict[str, Any]] = []
    seen_risks: set[tuple[str, str]] = set()  # one line per (transition, wording)
    for m in sorted(metrics, key=lambda x: (RAG_RANK.get(x.rag, 9), x.id)):
        for text in _critical_gaps(m, critical)[:3]:
            risks.append({"transition_id": m.id, "text": text, "kind": "critical gap"})
        if m.transition.blocker_note:
            seen_risks.add((m.id, " ".join(m.transition.blocker_note.lower().split()).rstrip(".")))
            risks.append(
                {
                    "transition_id": m.id,
                    "text": f"{m.transition.name}: {_short(m.transition.blocker_note, 120)}",
                    "kind": "blocker",
                }
            )
    top_rating = (cfg.option_values(db, "risk_ratings") or ["High"])[0]  # the most serious rating
    for risk in db.scalars(
        select(Risk).where(Risk.transition_id.in_(ids), Risk.rating == top_rating).order_by(Risk.id)
    ).all():
        m = by_id[risk.transition_id]
        name = m.transition.name
        linked = [i for i in m.items if i.playbook_item_id in (risk.item_ids or [])]
        if linked and not any(
            i.status in GAP_STATUSES and i.applicability == "Applies" and not i.covered
            for i in linked
        ):
            continue  # every linked item is complete or covered (e.g. by an approved exception)
        key = (risk.transition_id, " ".join(risk.title.lower().split()).rstrip("."))
        if key in seen_risks:
            continue
        seen_risks.add(key)
        risks.append(
            {
                "transition_id": risk.transition_id,
                "text": f"{name}: {_short(risk.title, 100)} (high risk)",
                "kind": "risk",
            }
        )
    risks = risks[:MAX_RISKS]

    horizon = today + timedelta(days=cfg.thresholds(db)["leadership_decision_window_days"])
    decisions = []
    for m in sorted(metrics, key=lambda x: (x.transition.next_decision_date or horizon, x.id)):
        t = m.transition
        if t.next_decision_date is not None and today <= t.next_decision_date <= horizon:
            decisions.append(
                {
                    "transition_id": t.id,
                    "name": t.name,
                    "gate_short": GATE_SHORT.get(t.current_gate, t.current_gate),
                    "date": t.next_decision_date.isoformat(),
                    "days": (t.next_decision_date - today).days,
                    "rag": m.rag,
                }
            )

    approvals = _recent_approvals(db, ids, by_id, users, today)

    asks: list[str] = []
    for c in db.scalars(
        select(Condition)
        .where(Condition.transition_id.in_(ids), Condition.status == "Open")
        .order_by(Condition.id)
    ).all()[:4]:
        owner = users.get(c.owner_user_id or "")
        asks.append(
            f"{by_id[c.transition_id].transition.name}: close {c.id} ({_short(c.text, 60)})"
            + (f", owner {owner.name}" if owner else "")
        )
    for ex in db.scalars(
        select(ExceptionRecord)
        .where(ExceptionRecord.transition_id.in_(ids), ExceptionRecord.status.like("Pending%"))
        .order_by(ExceptionRecord.ref)
    ).all()[:3]:
        asks.append(
            f"{by_id[ex.transition_id].transition.name}: decision needed on exception {ex.ref}"
        )
    overdue = Counter(
        a.transition_id
        for a in db.scalars(
            select(Action).where(
                Action.transition_id.in_(ids),
                Action.status.in_(OPEN_ACTION),
                Action.due_date.is_not(None),
                Action.due_date < today,
            )
        ).all()
    )
    for tid, n in sorted(overdue.items()):
        asks.append(f"{by_id[tid].transition.name}: {n} overdue action(s) need an owner push")

    wins = [
        f"{a['type']} approved for {a['name']} on {_human_date(a['date'])}"
        + (f" ({a['approver']})" if a.get("approver") else "")
        for a in approvals
        if (today - date.fromisoformat(a["date"])).days <= RECENT_WIN_DAYS
    ]
    since = clock.now() - timedelta(days=RECENT_WIN_DAYS)
    for c in db.scalars(
        select(Condition).where(
            Condition.transition_id.in_(ids),
            Condition.status == "Closed",
            Condition.closed_at >= since,
        )
    ).all():
        wins.append(f"{by_id[c.transition_id].transition.name}: condition {c.id} closed")
    wins += [
        f"{r['name']} is on track (Green)"
        for r in rows
        if r["rag"] == "Green" and r["critical_gaps"] == 0
    ][:3]

    return {
        "scope": scope,
        "scope_id": scope_id,
        "title": title,
        "today": today.isoformat(),
        "transitions": rows,
        "portfolios": portfolios,
        "risks": risks,
        "decisions_next_30_days": decisions,
        "approvals": approvals,
        "asks": asks,
        "wins": wins,
    }


def _recent_approvals(
    db: Session,
    ids: list[str],
    by_id: dict[str, TransitionMetrics],
    users: dict[str, User],
    today: Any,
) -> list[dict[str, Any]]:
    since = clock.now() - timedelta(days=RECENT_APPROVAL_DAYS)
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    reviews = db.scalars(
        select(GateReview)
        .where(
            GateReview.transition_id.in_(ids),
            GateReview.gate_type == "decision",
            GateReview.decided_at >= since,
        )
        .order_by(GateReview.decided_at.desc(), GateReview.id.desc())
    ).all()
    for r in reviews:
        if not r.outcome.startswith("Approve") or (r.transition_id, r.gate) in seen:
            continue
        seen.add((r.transition_id, r.gate))
        who = users.get(r.decided_by or "")
        out.append(
            {
                "transition_id": r.transition_id,
                "name": by_id[r.transition_id].transition.name,
                "type": GATE_SHORT.get(r.gate, r.gate),
                "date": r.decided_at.date().isoformat(),
                "approver": who.name if who else "",
                "outcome": r.outcome,
            }
        )
    requests = db.scalars(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.transition_id.in_(ids),
            ApprovalRequest.type.in_(("AtD", "AtO")),
            ApprovalRequest.status == "Approved",
            ApprovalRequest.decided_at >= since,
        )
        .order_by(ApprovalRequest.decided_at.desc(), ApprovalRequest.id.desc())
    ).all()
    for q in requests:
        key = (q.transition_id, q.gate or "")
        if key in seen or q.decided_at is None:
            continue
        seen.add(key)
        last = sorted(q.steps, key=lambda s: s.step)[-1] if q.steps else None
        who = users.get(last.decided_by or "") if last else None
        out.append(
            {
                "transition_id": q.transition_id,
                "name": by_id[q.transition_id].transition.name,
                "type": q.type,
                "date": q.decided_at.date().isoformat(),
                "approver": who.name if who else "",
                "outcome": "Approved (chain complete)",
            }
        )
    return sorted(out, key=lambda a: (a["date"], a["transition_id"]), reverse=True)


def generate_update(
    db: Session, user: User, scope: LeadershipScope, scope_id: str | None
) -> LeadershipUpdate:
    """Collect data, call ``get_ai_service().leadership_update``, store a ``LeadershipUpdate`` row
    (generated_by=user.id), audit actor_type "Human" (the requesting user) note "Generated leadership
    update", flush. Caller must hold Perm.GENERATE_LEADERSHIP_UPDATE."""
    data = collect_scope_data(db, scope, scope_id)
    content = get_ai_service().leadership_update(data)
    row = LeadershipUpdate(
        scope=scope,
        scope_id=scope_id if scope != "all" else None,
        content_md=content,
        generated_by=user.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_ORION,  # Orion drafted it; the human sends it (BR-050)
        entity="LeadershipUpdate",
        entity_id=row.id,
        action="generated",
        transition_id=scope_id if scope == "transition" else None,
        after={"scope": scope, "scope_id": row.scope_id, "title": _title(row)},
        note=f"Orion drafted the leadership update for {user.name}",
    )
    return row


def markdown_to_html(markdown: str) -> str:
    """Small renderer for the update markdown (headings, bullets, tables, bold/italic), sanitised."""

    def inline(text: str) -> str:
        text = escape_text(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        return re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<em>\1</em>", text)

    out: list[str] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("## "):
            out.append(f"<h4>{inline(line[3:])}</h4>")
        elif line.startswith("# "):
            out.append(f"<h3>{inline(line[2:])}</h3>")
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in cells):
                    rows.append(cells)
                i += 1
            head, body = rows[0], rows[1:]
            html = (
                "<table><thead><tr>"
                + "".join(f"<th>{inline(c)}</th>" for c in head)
                + "</tr></thead>"
            )
            html += "<tbody>" + "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body
            )
            out.append(html + "</tbody></table>")
            continue
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
        i += 1
    return sanitize_html("".join(out))


def send_update(db: Session, update_id: int, user: User, to: list[str]) -> LeadershipUpdate:
    """Validate addresses (``domain.drafts.validate_addresses``; BadRequest 400 on invalid), send an
    HTML email via the mock MailService from ``ORION_MAILBOX`` (subject = update title, body =
    markdown rendered to sanitised HTML via ``domain.html_sanitize``), add an outbox row, set
    ``sent_at`` (clock-aware), record recipients, audit actor_type "Human" note "Sent leadership
    update to <n> recipients". NotFound 404 for unknown id. Re-sending is allowed."""
    row = db.get(LeadershipUpdate, update_id)
    if row is None:
        raise NotFound(f"Leadership update {update_id} not found")
    recipients, _cc = validate_addresses(to, [])
    related = [f"LU-{row.id}"] + (
        [row.scope_id] if row.scope == "transition" and row.scope_id else []
    )
    get_mail_service(db).send_mail(
        get_settings().orion_mailbox,
        recipients,
        [],
        _title(row),
        markdown_to_html(row.content_md),
        related,
    )
    row.sent_at = clock.now()
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="LeadershipUpdate",
        entity_id=row.id,
        action="sent",
        transition_id=row.scope_id if row.scope == "transition" else None,
        after={"to": recipients, "sent_at": row.sent_at},
        note=f"Sent leadership update to {len(recipients)} recipients",
    )
    return row


def _title(row: LeadershipUpdate) -> str:
    for line in row.content_md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Leadership update"


def _sent_to(db: Session, row: LeadershipUpdate) -> list[str]:
    event = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.entity == "LeadershipUpdate",
            AuditEvent.entity_id == str(row.id),
            AuditEvent.action == "sent",
        )
        .order_by(AuditEvent.id.desc())
    ).first()
    if event is None or not event.after:
        return []
    return [str(a) for a in event.after.get("to", [])]


def leadership_out(db: Session, row: LeadershipUpdate) -> LeadershipUpdateOut:
    """Map a row: title (first markdown heading), generated_by PersonRef, generated_source
    "Orion agent", sent_to from the latest outbox row / audit payload of this update."""
    author = db.get(User, row.generated_by) if row.generated_by else None
    return LeadershipUpdateOut(
        id=row.id,
        scope=row.scope,  # type: ignore[arg-type]
        scope_id=row.scope_id,
        title=_title(row),
        content_md=row.content_md,
        generated_by=PersonRef(id=author.id, name=author.name) if author else None,
        created_at=row.created_at,
        sent_at=row.sent_at,
        sent_to=_sent_to(db, row) if row.sent_at else [],
    )


def list_updates(db: Session) -> list[LeadershipUpdateOut]:
    """Newest first (created_at desc, id desc)."""
    rows = db.scalars(
        select(LeadershipUpdate).order_by(
            LeadershipUpdate.created_at.desc(), LeadershipUpdate.id.desc()
        )
    ).all()
    return [leadership_out(db, r) for r in rows]


def get_update(db: Session, update_id: int) -> LeadershipUpdateOut:
    """404 when unknown."""
    row = db.get(LeadershipUpdate, update_id)
    if row is None:
        raise NotFound(f"Leadership update {update_id} not found")
    return leadership_out(db, row)
