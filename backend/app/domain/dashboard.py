"""Role-aware dashboard (FR-010, spec §8.1).

"My transitions" = the involvement set of the user (see ``domain.transitions``), Active only.
Roles with "see all transitions" (Leadership) get portfolio-wide tiles and portfolio summaries instead of "My work".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from urllib.parse import urlencode

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app import clock
from app.config import get_settings
from app.domain import cfg
from app.domain.audit_text import describe_event
from app.domain.control_tower import build_kpis
from app.domain.metrics import ItemRow, TransitionMetrics, compute_metrics, plural, reference_lists
from app.domain.transitions import is_involved, sort_register
from app.models import Action, ApprovalRequest, ApprovalStep, AuditEvent, Transition, User
from app.permissions import Perm, has_perm
from app.rules.constants import GAP_STATUSES, GATE_ORDER, GATE_SHORT, is_open_status
from app.rules.rag import AMBER, GREEN, GREY, RED
from app.rules.readiness import round_half_up
from app.schemas.audit import AuditEventOut
from app.schemas.common import KpiTileOut, UserOut
from app.schemas.dashboard import DashboardOut, PortfolioTileOut, WorkItemOut

OPEN_ACTION_STATUSES = ("Open", "In progress")


def is_open_item(item: ItemRow, current_gate: str) -> bool:
    """An item still needing work at the current gate: Applies, open, due by now, not covered."""
    return (
        item.applicability == "Applies"
        and is_open_status(item.status)
        and GATE_ORDER[item.due_gate] <= GATE_ORDER[current_gate]
        and not item.covered
    )


def is_gap(item: ItemRow) -> bool:
    return item.status in GAP_STATUSES


@dataclass
class PendingApproval:
    request_id: str
    label: str
    transition_id: str
    transition_name: str
    waiting_days: int
    activated_on: date


def pending_approvals(db: Session, user: User) -> list[PendingApproval]:
    """Approval steps waiting for ``user``, oldest first. Same rule as the approvals inbox (A-57):
    the Pending step of a Pending request whose approver is the user, or that has no named approver
    and the user's role, or the CISO/BISO mock step for a role that may see mock approvals (IRM) in
    demo mode."""
    waiting_for_me = [
        ApprovalStep.approver_user_id == user.id,
        and_(ApprovalStep.approver_user_id.is_(None), ApprovalStep.role == user.role),
    ]
    if has_perm(user.role, Perm.SEE_MOCK_APPROVALS) and get_settings().demo_mode:
        waiting_for_me.append(ApprovalStep.role == cfg.mock_approver(db)["mock_role"])
    rows = db.execute(
        select(ApprovalStep, ApprovalRequest, Transition.name)
        .join(ApprovalRequest, ApprovalRequest.id == ApprovalStep.request_id)
        .join(Transition, Transition.id == ApprovalRequest.transition_id)
        .where(
            ApprovalStep.status == "Pending",
            ApprovalRequest.status == "Pending",
            or_(*waiting_for_me),
        )
    ).all()
    today = clock.today()
    out = []
    for step, request, name in rows:
        started = (step.activated_at or request.created_at).date()
        out.append(
            PendingApproval(
                request_id=request.id,
                label=request.subject_label or f"{request.type} approval",
                transition_id=request.transition_id,
                transition_name=name,
                waiting_days=max((today - started).days, 0),
                activated_on=started,
            )
        )
    out.sort(key=lambda a: (a.activated_on, a.request_id))
    return out


def open_actions(db: Session, transition_ids: list[str], owner: str | None = None) -> list[Action]:
    """Open / In progress actions of the given transitions (optionally of one owner)."""
    if not transition_ids:
        return []
    query = select(Action).where(
        Action.transition_id.in_(transition_ids), Action.status.in_(OPEN_ACTION_STATUSES)
    )
    if owner is not None:
        query = query.where(Action.owner_user_id == owner)
    return list(db.scalars(query).all())


def _due_label_item(m: TransitionMetrics) -> str:
    short = GATE_SHORT[m.transition.current_gate]
    days = m.days_to_next_decision
    if days is None:
        return short
    if days < 0:
        return f"{short} · {plural(-days, 'day')} overdue"
    return f"{short} · {plural(days, 'day')}"


def _action_due_label(action: Action, today: date) -> str:
    if action.due_date is None:
        return "No due date"
    if action.due_date < today:
        return f"Overdue {plural((today - action.due_date).days, 'day')}"
    return f"Due {action.due_date.isoformat()}"


def _date_key(d: date | None) -> tuple[bool, date]:
    return (d is None, d or date.max)


def build_my_work(
    db: Session,
    user: User,
    mine: list[TransitionMetrics],
    approvals: list[PendingApproval] | None = None,
) -> tuple[list[WorkItemOut], int]:
    """Approvals, critical gaps, other gaps, my actions, my other open items (spec §8.1)."""
    today = clock.today()
    out: list[WorkItemOut] = []

    for a in pending_approvals(db, user) if approvals is None else approvals:
        out.append(
            WorkItemOut(
                kind="approval",
                id=a.request_id,
                title=a.label,
                transition_id=a.transition_id,
                transition_name=a.transition_name,
                status="Pending",
                lens=None,
                gap_severity=None,
                due_label=f"Waiting {plural(a.waiting_days, 'day')}",
                due_date=a.activated_on,
                link=f"/approvals?request={a.request_id}",
            )
        )

    critical: list[WorkItemOut] = []
    critical_severity = cfg.critical_severity(db)
    gaps: list[WorkItemOut] = []
    others: list[WorkItemOut] = []
    for m in mine:
        for item in m.items:
            if item.owner_user_id != user.id or not is_open_item(item, m.transition.current_gate):
                continue
            row = WorkItemOut(
                kind="item",
                id=item.playbook_item_id,
                title=item.title,
                transition_id=m.id,
                transition_name=m.transition.name,
                status=item.status,
                lens=item.lens,
                gap_severity=item.gap_severity if is_gap(item) else None,
                due_label=_due_label_item(m),
                due_date=m.transition.next_decision_date,
                link=f"/transitions/{m.id}/assessment?item={item.playbook_item_id}",
            )
            if is_gap(item) and item.gap_severity == critical_severity:
                critical.append(row)
            elif is_gap(item):
                gaps.append(row)
            else:
                others.append(row)
    for group in (critical, gaps, others):
        group.sort(key=lambda w: (_date_key(w.due_date), w.transition_id, w.id))

    names = {m.id: m.transition.name for m in mine}
    actions = open_actions(db, [m.id for m in mine], owner=user.id)
    actions.sort(key=lambda a: (_date_key(a.due_date), a.id))
    action_rows = [
        WorkItemOut(
            kind="action",
            id=a.id,
            title=a.title,
            transition_id=a.transition_id,
            transition_name=names.get(a.transition_id, a.transition_id),
            status=a.status,
            lens=None,
            gap_severity=None,
            due_label=_action_due_label(a, today),
            due_date=a.due_date,
            link=f"/transitions/{a.transition_id}/gaps?action={a.id}",
        )
        for a in actions
    ]

    out += critical + gaps + action_rows + others
    return out[: cfg.thresholds(db)["dashboard"]["my_work_limit"]], len(out)


def build_recent_activity(db: Session, names: dict[str, str]) -> list[AuditEventOut]:
    """Latest audit events (recent_activity_limit) whose transition is one of mine (``names``: id -> name), newest first."""
    if not names:
        return []
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.transition_id.in_(list(names)))
        .order_by(AuditEvent.at.desc(), AuditEvent.id.desc())
        .limit(cfg.thresholds(db)["dashboard"]["recent_activity_limit"])
    ).all()
    actor_ids = {e.actor_user_id for e in events if e.actor_user_id}
    users = (
        {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(actor_ids))).all()}
        if actor_ids
        else {}
    )
    return [
        AuditEventOut(
            id=e.id,
            at=e.at,
            actor_user_id=e.actor_user_id,
            actor_name=users.get(e.actor_user_id) if e.actor_user_id else None,
            actor_type=e.actor_type,
            transition_id=e.transition_id,
            transition_name=names.get(e.transition_id) if e.transition_id else None,
            entity=e.entity,
            entity_id=e.entity_id,
            action=e.action,
            before=e.before,
            after=e.after,
            note=e.note,
            summary=describe_event(e.entity, e.entity_id, e.action, e.after, e.note or ""),
        )
        for e in events
    ]


def _leadership_kpis(rows: list[TransitionMetrics]) -> list[KpiTileOut]:
    """Portfolio-wide tiles (active, red, decisions, critical) linking to the control tower."""
    wanted = {"active", "red", "decisions_14d", "critical"}
    tiles = []
    for tile in build_kpis(rows):
        if tile.key not in wanted:
            continue
        tile.link = "/control-tower?" + urlencode(tile.filter)
        tiles.append(tile)
    return tiles


def build_portfolio_tiles(
    rows: list[TransitionMetrics], portfolios: list[str]
) -> list[PortfolioTileOut]:
    tiles = []
    for name in portfolios:
        group = [m for m in rows if m.transition.portfolio == name]
        scores = [m.readiness.overall for m in group if m.launched]  # A-34
        tiles.append(
            PortfolioTileOut(
                portfolio=name,
                transitions=len(group),
                red=sum(1 for m in group if m.rag == RED),
                amber=sum(1 for m in group if m.rag == AMBER),
                green=sum(1 for m in group if m.rag == GREEN),
                grey=sum(1 for m in group if m.rag == GREY),
                average_readiness=(
                    round_half_up(Fraction(sum(scores), len(scores))) if scores else None
                ),
                decisions_14d=sum(
                    1
                    for m in group
                    if m.days_to_next_decision is not None and m.days_to_next_decision <= 14
                ),
                critical_gaps=sum(m.critical_gaps for m in group),
            )
        )
    return tiles


def _my_kpis(
    user: User, mine: list[TransitionMetrics], open_items: int, approvals: int
) -> list[KpiTileOut]:
    critical = sum(m.critical_gaps for m in mine)
    decisions = sum(
        1 for m in mine if m.days_to_next_decision is not None and m.days_to_next_decision <= 14
    )
    tiles = [
        KpiTileOut(
            key="my_open_items",
            label="My open items",
            value=open_items,
            hint="Checklist items only (approvals and actions are counted separately): items I own "
            "that are due by the current gate and not yet done",
        ),
        KpiTileOut(
            key="my_pending_approvals",
            label="My pending approvals",
            value=approvals,
            tone="warning" if approvals else "neutral",
            hint="Approval steps waiting for me",
            link="/approvals",
        ),
    ]
    if user.role == "OR_FOCAL":
        tiles.append(
            KpiTileOut(
                key="transitions_i_own",
                label="Transitions I own",
                value=sum(1 for m in mine if m.transition.or_focal_user_id == user.id),
                hint="Active transitions where I am the OR focal",
                link="/transitions?mine=true",
            )
        )
    tiles += [
        KpiTileOut(
            key="decisions_14d",
            label="Decisions due in 14 days",
            value=decisions,
            tone="warning" if decisions else "neutral",
            hint="Next gate decision within 14 days in my transitions",
            link="/transitions?mine=true&decision_within_days=14",
        ),
        KpiTileOut(
            key="critical_gaps",
            label="Critical gaps/risks",
            value=critical,
            tone="danger" if critical > 0 else "neutral",
            hint="Open critical gaps/risks in my transitions",
            link="/transitions?mine=true&has_critical=true",
        ),
    ]
    return tiles


def _subtitle(db: Session, user: User, mine: list[Transition]) -> str:
    """Role label plus the (distinct, sorted) portfolios of the user's active transitions."""
    portfolios = sorted({t.portfolio for t in mine if t.portfolio})
    shown = ", ".join(portfolios[:3]) + (
        f" +{len(portfolios) - 3} more" if len(portfolios) > 3 else ""
    )
    label = cfg.role_label(db, user.role)
    return f"{label} · {shown}" if shown else label


def build_dashboard(db: Session, user: User) -> DashboardOut:
    """One metrics computation per request. A role that sees all transitions computes the whole portfolio once and takes
    "mine" (Active) from it; every other role computes only its own Active transitions."""
    active = db.scalars(select(Transition).where(Transition.status == "Active")).all()
    mine_rows = [t for t in active if is_involved(user, t)]
    sees_all = has_perm(user.role, Perm.SEE_ALL_TRANSITIONS)
    if sees_all:
        everything = compute_metrics(db, list(db.scalars(select(Transition)).all()))
        mine_ids = {t.id for t in mine_rows}
        mine = sort_register([m for m in everything if m.id in mine_ids])
    else:
        everything = []
        mine = sort_register(compute_metrics(db, mine_rows))
    names = {m.id: m.transition.name for m in mine}
    me = UserOut.model_validate(user)
    me.role_label = cfg.role_label(db, user.role)
    base = dict(
        user=me,
        subtitle=_subtitle(db, user, mine_rows),
        today=clock.today(),
        recent_activity=build_recent_activity(db, names),
    )

    if sees_all:
        ref = reference_lists(db)
        return DashboardOut(
            **base,
            kpis=_leadership_kpis(everything),
            my_work=[],
            my_work_total=0,
            portfolio_tiles=build_portfolio_tiles(everything, ref["portfolios"]),
        )

    approvals = pending_approvals(db, user)
    work, total = build_my_work(db, user, mine, approvals)
    open_items = sum(
        1
        for m in mine
        for i in m.items
        if i.owner_user_id == user.id and is_open_item(i, m.transition.current_gate)
    )
    return DashboardOut(
        **base,
        kpis=_my_kpis(user, mine, open_items, len(approvals)),
        my_work=work,
        my_work_total=total,
        portfolio_tiles=[],
    )
