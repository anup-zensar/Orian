"""Admin configuration domain logic (FR-100). M9.

All writes are audited (actor_type "Human"). Playbook edits never alter existing transition items
(spec 8.16 notice). Never delete rows used by transitions.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import access
from app.domain import audit, cfg
from app.domain.config_admin import check_autonomy_lowered
from app.errors import BadRequest, NotFound
from app.models import (
    ApprovalChainConfig,
    ApprovalRequest,
    EvalTarget,
    FlavourRule,
    PlaybookItem,
    Portfolio,
    ReminderRule,
    User,
)
from app.rules.constants import ACTOR_HUMAN, GATES, LENSES
from app.schemas.admin import (
    ApprovalCancelIn,
    ApprovalCancelOut,
    ApprovalChainOut,
    ApprovalChainsIn,
    ApprovalChainsOut,
    ChainStep,
    EvalMetricOut,
    EvalTargetsIn,
    EvalTargetsOut,
    EvalTierTargetOut,
    FlavourRuleOut,
    FlavourRulesIn,
    FlavourRulesOut,
    GoldenSetIn,
    GoldenSetItemOut,
    GoldenSetOut,
    PlaybookItemAdminOut,
    PlaybookItemUpdateIn,
    ReminderRuleOut,
    ReminderRulesIn,
)

MOCK_ROLE = "CISO_BISO"  # the mocked approval role (IRM acts for it in demo mode)
CHAIN_ORDER = ("OCET", "AtD", "AtO", "SUPPORT_MODEL", "EXCEPTION")
ITEM_FIELDS = ("title", "description", "gate", "lens", "applicable_tiers", "mandatory", "active")


def _audit(
    db: Session,
    user: User,
    entity: str,
    entity_id: str | int,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    note: str = "",
) -> None:
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity=entity,
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
        note=note,
    )


# --- playbook items ---------------------------------------------------------------------------
def _item_out(item: PlaybookItem) -> PlaybookItemAdminOut:
    out = PlaybookItemAdminOut.model_validate(item)
    out.lens_suggested = item.lens_is_suggested
    out.applicable_tiers = list(item.applicable_tiers or [])
    return out


def _validate_gate_lens(gate: str, lens: str) -> list[str]:
    reasons = []
    if gate not in GATES:
        reasons.append(f"Unknown gate '{gate}'")
    if lens not in LENSES:
        reasons.append(f"Unknown lens '{lens}'")
    return reasons


def list_playbook_items(
    db: Session,
    *,
    source: str | None,
    q: str | None,
    gate: str | None,
    lens: str | None,
    active: bool | None,
) -> list[PlaybookItemAdminOut]:
    """Filtered library (q = case-insensitive match on id/title/description), ordered by id."""
    sources = [c.code for c in cfg.checklist_defs(db, active_only=False)]
    if source is not None and source not in sources:
        raise BadRequest("Invalid source", [f"source must be one of {', '.join(sources)}"])
    stmt = select(PlaybookItem).order_by(PlaybookItem.id)
    if source:
        stmt = stmt.where(PlaybookItem.source == source)
    if gate:
        stmt = stmt.where(PlaybookItem.gate == gate)
    if lens:
        stmt = stmt.where(PlaybookItem.lens == lens)
    if active is not None:
        stmt = stmt.where(PlaybookItem.active == active)
    rows = list(db.scalars(stmt).all())
    if q and q.strip():
        needle = q.strip().lower()
        rows = [
            r
            for r in rows
            if needle in r.id.lower()
            or needle in (r.title or "").lower()
            or needle in (r.description or "").lower()
        ]
    return [_item_out(r) for r in rows]


def _load_item(db: Session, item_id: str) -> PlaybookItem:
    item = db.get(PlaybookItem, item_id)
    if item is None:
        raise NotFound(f"Playbook item {item_id} not found")
    return item


def get_playbook_item(db: Session, item_id: str) -> PlaybookItemAdminOut:
    """404 when unknown."""
    return _item_out(_load_item(db, item_id))


def update_playbook_item(
    db: Session, item_id: str, body: PlaybookItemUpdateIn, user: User
) -> PlaybookItemAdminOut:
    """Apply edit; a lens change clears ``lens_is_suggested``; audit entity "PlaybookItem" with
    before/after. 404 unknown, 422 unknown gate / tiers outside 1..4."""
    access.ensure_admin(user, "edit the playbook")
    item = _load_item(db, item_id)
    reasons = _validate_gate_lens(body.gate, body.lens)
    tiers = cfg.tier_numbers(db)
    if any(t not in tiers for t in body.applicable_tiers):
        reasons.append(f"applicable_tiers must be within {tiers[0]}..{tiers[-1]}")
    if reasons:
        raise BadRequest("Invalid playbook item", reasons)
    before = audit.snapshot(item, ITEM_FIELDS)
    if body.lens != item.lens:
        item.lens_is_suggested = False
    item.title = body.title
    item.description = body.description
    item.gate = body.gate
    item.lens = body.lens
    item.applicable_tiers = sorted(set(body.applicable_tiers))
    item.mandatory = body.mandatory
    item.active = body.active
    db.flush()
    after = audit.snapshot(item, ITEM_FIELDS)
    _audit(db, user, "PlaybookItem", item.id, "updated", before, after)
    return _item_out(item)


# --- flavour rules ----------------------------------------------------------------------------
def _flavour_out(db: Session) -> FlavourRulesOut:
    rows = db.scalars(select(FlavourRule).order_by(FlavourRule.sort_order)).all()
    return FlavourRulesOut(rules=[FlavourRuleOut.model_validate(r) for r in rows])


def get_flavour_rules(db: Session) -> FlavourRulesOut:
    """All flavour rules."""
    return _flavour_out(db)


def put_flavour_rules(db: Session, body: FlavourRulesIn, user: User) -> FlavourRulesOut:
    """Update rules; audit entity "FlavourRule" per changed row. 422 unknown project_type."""
    access.ensure_admin(user, "change flavour rules")
    existing = {r.project_type: r for r in db.scalars(select(FlavourRule)).all()}
    unknown = [r.project_type for r in body.rules if r.project_type not in existing]
    if unknown:
        raise BadRequest("Unknown project type", [f"Unknown project type '{u}'" for u in unknown])
    known = {c.code for c in cfg.checklist_defs(db)}
    reasons = [
        f"{r.project_type}: at least one checklist is required (a type without items is unusable)"
        for r in body.rules
        if not r.checklists
    ]
    reasons += [
        f"{r.project_type}: '{code}' is not an active checklist"
        for r in body.rules
        for code in r.checklists
        if code not in known
    ]
    if reasons:
        raise BadRequest("Invalid flavour rules", reasons)
    for entry in body.rules:
        row = existing[entry.project_type]
        fields = ("checklists", "requires_tiering", "note")
        before = audit.snapshot(row, fields)
        row.checklists = list(dict.fromkeys(entry.checklists))
        row.requires_tiering = entry.requires_tiering
        row.note = entry.note
        after = audit.snapshot(row, fields)
        if before != after:
            _audit(db, user, "FlavourRule", row.project_type, "updated", before, after)
    db.flush()
    return _flavour_out(db)


# --- golden set -------------------------------------------------------------------------------
def _portfolio(db: Session, name: str) -> Portfolio:
    portfolio = db.get(Portfolio, name)
    if portfolio is None:
        raise NotFound(f"Portfolio '{name}' not found")
    return portfolio


def _golden_out(db: Session, portfolio: Portfolio) -> GoldenSetOut:
    rows = db.scalars(
        select(PlaybookItem)
        .where(PlaybookItem.source == "PORTFOLIO", PlaybookItem.portfolio == portfolio.name)
        .order_by(PlaybookItem.sort_order, PlaybookItem.id)
    ).all()
    return GoldenSetOut(
        portfolio=portfolio.name,
        focus_areas=list(portfolio.focus_areas or []),
        items=[
            GoldenSetItemOut(
                id=r.id,
                title=r.title,
                gate=r.gate,
                owner_role_hint=r.owner_role_hint or "",
                lens=r.lens,
                mandatory=r.mandatory,
                active=r.active,
            )
            for r in rows
        ],
    )


def get_golden_set(db: Session, portfolio: str) -> GoldenSetOut:
    """404 unknown portfolio."""
    return _golden_out(db, _portfolio(db, portfolio))


def put_golden_set(db: Session, portfolio: str, body: GoldenSetIn, user: User) -> GoldenSetOut:
    """Replace list: new ids "<CODE>-NN" (next free number), edit existing, deactivate omitted
    ones (active=False; never delete rows). Audit entity "PlaybookItem" per change. 404/422."""
    access.ensure_admin(user, "change golden sets")
    pf = _portfolio(db, portfolio)
    existing = {
        r.id: r
        for r in db.scalars(
            select(PlaybookItem).where(
                PlaybookItem.source == "PORTFOLIO", PlaybookItem.portfolio == pf.name
            )
        ).all()
    }
    reasons: list[str] = []
    seen: set[str] = set()
    for entry in body.items:
        reasons.extend(_validate_gate_lens(entry.gate, entry.lens))
        if entry.id:
            if entry.id not in existing:
                reasons.append(f"Item '{entry.id}' is not in the {pf.name} golden set")
            elif entry.id in seen:
                reasons.append(f"Item '{entry.id}' is listed twice")
            seen.add(entry.id)
    if reasons:
        raise BadRequest("Invalid golden set", list(dict.fromkeys(reasons)))

    fields = ("title", "gate", "owner_role_hint", "lens", "mandatory", "active")
    prefix = f"{pf.code}-"
    numbers = [
        int(i[len(prefix) :])
        for i in db.scalars(select(PlaybookItem.id).where(PlaybookItem.id.like(f"{prefix}%"))).all()
        if i[len(prefix) :].isdigit()
    ]
    next_no = max(numbers) + 1 if numbers else 1
    max_sort = max([r.sort_order for r in existing.values()], default=-1)

    for entry in body.items:
        if entry.id:
            row = existing[entry.id]
            before = audit.snapshot(row, fields)
            if entry.lens != row.lens:
                row.lens_is_suggested = False
            row.title = entry.title
            row.gate = entry.gate
            row.owner_role_hint = entry.owner_role_hint
            row.lens = entry.lens
            row.mandatory = entry.mandatory
            row.mandatory_rule = "always" if entry.mandatory else None
            row.active = True
            after = audit.snapshot(row, fields)
            if before != after:
                _audit(db, user, "PlaybookItem", row.id, "updated", before, after)
        else:
            new_id = f"{prefix}{next_no:02d}"
            next_no += 1
            max_sort += 1
            row = PlaybookItem(
                id=new_id,
                source="PORTFOLIO",
                source_label="Portfolio golden set (admin)",
                portfolio=pf.name,
                title=entry.title,
                gate=entry.gate,
                lens=entry.lens,
                category="Portfolio golden set",
                kind="Deliverable",
                mandatory=entry.mandatory,
                mandatory_rule="always" if entry.mandatory else None,
                applies_to_project_types=[],  # [] = every project type, also future ones
                owner_role_hint=entry.owner_role_hint,
                active=True,
                sort_order=max_sort,
            )
            db.add(row)
            db.flush()
            _audit(db, user, "PlaybookItem", new_id, "created", None, audit.snapshot(row, fields))
    for item_id, row in existing.items():
        if item_id not in seen and row.active:
            before = audit.snapshot(row, fields)
            row.active = False
            _audit(
                db,
                user,
                "PlaybookItem",
                item_id,
                "deactivated",
                before,
                audit.snapshot(row, fields),
            )
    if body.focus_areas is not None and list(body.focus_areas) != list(pf.focus_areas or []):
        _audit(
            db,
            user,
            "Portfolio",
            pf.name,
            "updated",
            {"focus_areas": list(pf.focus_areas or [])},
            {"focus_areas": list(body.focus_areas)},
        )
        pf.focus_areas = list(body.focus_areas)
    db.flush()
    return _golden_out(db, pf)


# --- eval targets -----------------------------------------------------------------------------
def get_eval_targets(db: Session) -> EvalTargetsOut:
    """Grid of metrics by tier plus the confirmed flag."""
    rows = db.scalars(
        select(EvalTarget).order_by(EvalTarget.sort_order, EvalTarget.metric_id, EvalTarget.tier)
    ).all()
    metrics: dict[str, EvalMetricOut] = {}
    for r in rows:
        m = metrics.setdefault(
            r.metric_id,
            EvalMetricOut(
                metric_id=r.metric_id, metric=r.metric, evaluation=r.evaluation, tiers=[]
            ),
        )
        m.tiers.append(
            EvalTierTargetOut(
                tier=r.tier,
                target_text=r.target_text,
                operator=r.operator,
                value=r.value,
                unit=r.unit,
            )
        )
    return EvalTargetsOut(
        confirmed=bool(rows) and all(r.confirmed for r in rows), metrics=list(metrics.values())
    )


def put_eval_targets(db: Session, body: EvalTargetsIn, user: User) -> EvalTargetsOut:
    """Update targets per metric/tier and the confirmed flag (on all rows); audit "EvalTarget".
    422 unknown metric_id or tier."""
    access.ensure_admin(user, "change eval targets")
    rows = {(r.metric_id, r.tier): r for r in db.scalars(select(EvalTarget)).all()}
    metric_ids = {k[0] for k in rows}
    reasons: list[str] = []
    for metric in body.metrics:
        if metric.metric_id not in metric_ids:
            reasons.append(f"Unknown metric '{metric.metric_id}'")
            continue
        for t in metric.tiers:
            if (metric.metric_id, t.tier) not in rows:
                reasons.append(f"{metric.metric_id} has no tier {t.tier}")
            if t.value is not None and t.operator is None:
                reasons.append(f"{metric.metric_id} tier {t.tier}: a value needs an operator")
    if reasons:
        raise BadRequest("Invalid eval targets", reasons)
    fields = ("target_text", "operator", "value", "unit")
    for metric in body.metrics:
        for t in metric.tiers:
            row = rows[(metric.metric_id, t.tier)]
            before = audit.snapshot(row, fields)
            row.target_text = t.target_text
            row.operator = t.operator
            row.value = t.value
            row.unit = t.unit
            after = audit.snapshot(row, fields)
            if before != after:
                _audit(
                    db,
                    user,
                    "EvalTarget",
                    f"{metric.metric_id}/T{t.tier}",
                    "updated",
                    before,
                    after,
                )
    flag_before = all(r.confirmed for r in rows.values()) if rows else False
    for row in rows.values():
        row.confirmed = body.confirmed
    if flag_before != body.confirmed:
        _audit(
            db,
            user,
            "EvalTarget",
            "confirmed",
            "updated",
            {"confirmed": flag_before},
            {"confirmed": body.confirmed},
        )
    db.flush()
    return get_eval_targets(db)


# --- approval chains --------------------------------------------------------------------------
NEVER_APPROVE = ("ADMIN", "LEADERSHIP")
MAX_CHAIN_STEPS = 8


def chain_roles(db: Session) -> list[str]:
    """Roles that may sit on an approval step: every active role that can approve, plus the mock role.
    The Admin has no workflow override and Leadership only reads, so neither approves."""
    return [r.code for r in cfg.roles(db) if r.can_approve and r.code not in NEVER_APPROVE] + [
        MOCK_ROLE
    ]


def get_approval_chains(db: Session) -> ApprovalChainsOut:
    """All chains plus allowed roles."""
    rows = {r.type: r for r in db.scalars(select(ApprovalChainConfig)).all()}
    order = [t for t in CHAIN_ORDER if t in rows] + sorted(t for t in rows if t not in CHAIN_ORDER)
    chains = [
        ApprovalChainOut(
            type=t,  # type: ignore[arg-type]
            steps=[ChainStep(**s) for s in rows[t].steps],
            label=rows[t].label,
        )
        for t in order
    ]
    return ApprovalChainsOut(chains=chains, roles=chain_roles(db))


def put_approval_chains(db: Session, body: ApprovalChainsIn, user: User) -> ApprovalChainsOut:
    """Replace steps (and the display name) per chain type: at least one step, numbered 1..n, role
    from ``chain_roles``; the mock role is always a mocked step. Audit "config:approval_chains".
    Existing approval requests keep their steps."""
    access.ensure_admin(user, "change approval chains")
    reasons: list[str] = []
    staffed = set(db.scalars(select(User.role).where(User.active.is_(True)).distinct()).all())
    allowed = chain_roles(db)
    for chain in body.chains:
        if not chain.steps:
            reasons.append(f"{chain.type}: at least one step is required")
        if len(chain.steps) > MAX_CHAIN_STEPS:
            reasons.append(f"{chain.type}: at most {MAX_CHAIN_STEPS} steps")
        if [s.step for s in chain.steps] != list(range(1, len(chain.steps) + 1)):
            reasons.append(f"{chain.type}: steps must be numbered 1..{len(chain.steps)} in order")
        for s in chain.steps:
            if s.role not in allowed:
                reasons.append(f"{chain.type} step {s.step}: invalid role '{s.role}'")
            elif s.role != MOCK_ROLE and s.role not in staffed:
                # the mock role is the documented mock step (IRM approves in demo mode).
                reasons.append(
                    f"{chain.type} step {s.step}: no active user has role '{s.role}', "
                    "so the step could never be approved"
                )
    if reasons:
        raise BadRequest("Invalid approval chains", reasons)
    for chain in body.chains:
        row = db.get(ApprovalChainConfig, chain.type)
        new_steps = [
            dict(s.model_dump(), is_mock=s.is_mock or s.role == MOCK_ROLE) for s in chain.steps
        ]
        label = (chain.label or "").strip() or None
        if row is None:
            db.add(ApprovalChainConfig(type=chain.type, steps=new_steps, label=label))
            _audit(
                db,
                user,
                "config:approval_chains",
                chain.type,
                "created",
                None,
                {"steps": new_steps, "label": label},
            )
            continue
        before = {"steps": list(row.steps), "label": row.label}
        if row.steps != new_steps or row.label != label:
            row.steps = new_steps
            row.label = label
            _audit(
                db,
                user,
                "config:approval_chains",
                chain.type,
                "updated",
                before,
                {"steps": new_steps, "label": label},
            )
    db.flush()
    return get_approval_chains(db)


# --- reminder rules ---------------------------------------------------------------------------
def list_reminder_rules(db: Session) -> list[ReminderRuleOut]:
    """Ordered by sort_order."""
    rows = db.scalars(select(ReminderRule).order_by(ReminderRule.sort_order, ReminderRule.id)).all()
    return [ReminderRuleOut.model_validate(r) for r in rows]


def _check_reminder_params(db: Session, rule: ReminderRule, params: dict[str, Any]) -> list[str]:
    """Numeric thresholds are whole numbers 1..3650; R6 may also name the items it asks about
    (``item_ids``, existing library ids) and a ``category`` of the library."""
    reasons: list[str] = []
    for key, val in params.items():
        if rule.id == "R6" and key == "item_ids":
            ids = val if isinstance(val, list) and all(isinstance(v, str) for v in val) else None
            known = set(db.scalars(select(PlaybookItem.id).where(PlaybookItem.id.in_(ids or []))))
            if ids is None:
                reasons.append("R6: 'item_ids' must be a list of item ids")
            else:
                reasons += [f"R6: unknown playbook item '{i}'" for i in ids if i not in known]
        elif rule.id == "R6" and key == "category":
            if not isinstance(val, str) or len(val) > 120:
                reasons.append("R6: 'category' must be text of at most 120 characters")
        elif key not in (rule.params or {}):
            reasons.append(f"{rule.id}: unknown parameter '{key}'")
        elif isinstance(val, bool) or not isinstance(val, int) or not 0 < val <= 3650:
            reasons.append(f"{rule.id}: '{key}' must be a whole number from 1 to 3650")
    return reasons


def put_reminder_rules(db: Session, body: ReminderRulesIn, user: User) -> list[ReminderRuleOut]:
    """Update enabled, params and (only downwards) autonomous_eligible per rule id; audit
    "config:reminder_rules". 422 unknown id / bad params / autonomy switched on."""
    access.ensure_admin(user, "change reminder rules")
    rows = {r.id: r for r in db.scalars(select(ReminderRule)).all()}
    reasons: list[str] = []
    for entry in body.rules:
        row = rows.get(entry.id)
        if row is None:
            reasons.append(f"Unknown reminder rule '{entry.id}'")
            continue
        reasons += _check_reminder_params(db, row, entry.params)
        if entry.autonomous_eligible is not None:
            reasons += check_autonomy_lowered(
                row.id, row.autonomous_eligible, entry.autonomous_eligible
            )
    if reasons:
        raise BadRequest("Invalid reminder rules", reasons)
    for entry in body.rules:
        row = rows[entry.id]
        before = {
            "enabled": row.enabled,
            "params": dict(row.params or {}),
            "autonomous_eligible": row.autonomous_eligible,
        }
        row.enabled = entry.enabled
        row.params = {**(row.params or {}), **entry.params}
        if entry.autonomous_eligible is not None:
            row.autonomous_eligible = entry.autonomous_eligible
        after = {
            "enabled": row.enabled,
            "params": dict(row.params),
            "autonomous_eligible": row.autonomous_eligible,
        }
        if before != after:
            _audit(db, user, "config:reminder_rules", row.id, "updated", before, after)
    db.flush()
    return list_reminder_rules(db)


# --- stuck approvals --------------------------------------------------------------------------


def cancel_approval_request(
    db: Session, request_id: str, body: ApprovalCancelIn, user: User
) -> ApprovalCancelOut:
    """Cancel a stuck Pending approval request (e.g. the approver left). Admin only; the reason is
    required and stored on the audit event. Completion hooks do not run: the subject stays as it is
    and its owner starts a new request. 404 unknown, 409 already finished."""
    from app.domain import approvals

    access.ensure_admin(user, "cancel an approval request")
    request = db.get(ApprovalRequest, request_id)
    if request is None:
        raise NotFound(f"Approval request {request_id} not found")
    approvals.cancel_request(db, request=request, user=user, note=f"Admin cancelled: {body.reason}")
    return ApprovalCancelOut(request_id=request.id, status=request.status)
