"""Read side of the CR-01 admin API: builds every ``schemas.config_admin`` *Out* DTO.

The GET endpoints of ``routers/config_admin.py`` call these builders; the write endpoints (admin-API
engineer) call them too, to return "the saved section". Builders read the database through
``app.domain.cfg`` (cached) or directly where they need inactive rows or usage counts, and never
write anything.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app import access, permissions
from app.domain import cfg, cfg_defaults
from app.errors import BadRequest, NotFound
from app.models import (
    Action,
    AuditEvent,
    Condition,
    EvalTarget,
    Evidence,
    ExceptionRecord,
    HypercareDefect,
    OptionItem,
    OptionList,
    OrionDraft,
    PermissionText,
    PlaybookItem,
    Risk,
    RolePermission,
    Transition,
    TransitionItem,
    User,
)
from app.permissions import MATRIX, Perm
from app.rules.constants import GATE_ORDER
from app.schemas import config_admin as dto

STRUCTURAL_LOCK = "Behaviour depends on this value - only the label can change."

# option list key -> the columns that store its values (for "used by N")
USAGE_COLUMNS: dict[str, list[InstrumentedAttribute[Any]]] = {
    "regions": [Transition.region],
    "audience": [Transition.audience],
    "write_actions": [Transition.write_actions],
    "sensitive_data": [Transition.sensitive_data],
    "target_gate": [Transition.target_gate],
    "investment_type": [Transition.investment_type],
    "delivery_method": [Transition.delivery_method],
    "severities": [TransitionItem.gap_severity],
    "design_effectiveness": [TransitionItem.design_effectiveness],
    "evidence_types": [Evidence.type],
    "action_priorities": [Action.priority],
    "defect_priorities": [HypercareDefect.priority],
    "risk_ratings": [Risk.rating],
    # locked lists whose values are stored on records
    "evidence_statuses": [Evidence.status],
    "action_statuses": [Action.status],
    "condition_statuses": [Condition.status],
    "exception_statuses": [ExceptionRecord.status],
    "defect_statuses": [HypercareDefect.status],
    "draft_kinds": [OrionDraft.kind],
    "applicability": [TransitionItem.applicability],
    "item_statuses_business": [TransitionItem.status],
    "item_statuses_technical": [TransitionItem.status],
    "item_statuses_compliance": [TransitionItem.status],
    "actor_types": [AuditEvent.actor_type],
}


def _grouped_counts(db: Session, column: InstrumentedAttribute[Any]) -> dict[str, int]:
    """value -> number of rows holding it (one grouped query)."""
    return {
        str(value): int(n)
        for value, n in db.execute(
            select(column, func.count()).where(column.is_not(None)).group_by(column)
        ).all()
    }


def option_usage(db: Session, list_key: str) -> dict[str, int]:
    """value -> number of records using it: the stored columns of the built-in lists, plus the
    values held by custom fields that offer the list."""
    out: dict[str, int] = {}
    for column in USAGE_COLUMNS.get(list_key, []):
        for value, n in _grouped_counts(db, column).items():
            out[value] = out.get(value, 0) + n
    fields = [
        f.key
        for f in cfg.intake_fields(db, form=None, active_only=False)
        if f.option_list == list_key and not f.builtin
    ]
    if fields:
        for values in db.scalars(
            select(Transition.custom_fields).where(Transition.custom_fields.is_not(None))
        ):
            for key in fields:
                held = (values or {}).get(key)
                for value in held if isinstance(held, list) else [held]:
                    if value not in (None, ""):
                        out[str(value)] = out.get(str(value), 0) + 1
    return out


def usage_is_tracked(db: Session, list_key: str) -> bool:
    """True when ``option_usage`` knows every place a value of the list is stored, so an unused
    value can be removed safely (otherwise values are only ever deactivated)."""
    option_list = db.get(OptionList, list_key)
    return list_key in USAGE_COLUMNS or bool(option_list and not option_list.is_builtin)


def custom_field_usage(db: Session) -> dict[str, int]:
    """custom field key -> number of transitions holding a value (JSON, counted in Python)."""
    counts: dict[str, int] = {}
    for values in db.scalars(
        select(Transition.custom_fields).where(Transition.custom_fields.is_not(None))
    ):
        for key, value in (values or {}).items():
            if value not in (None, "", []):
                counts[key] = counts.get(key, 0) + 1
    return counts


# --------------------------------------------------------------------------- project types


def project_type_out(
    p: cfg.ProjectTypeCfg, used: dict[str, int] | None = None
) -> dto.ProjectTypeAdminOut:
    return dto.ProjectTypeAdminOut(
        code=p.code,
        label=p.label,
        description=p.description,
        active=p.active,
        sort_order=p.sort_order,
        checklists=list(p.checklists),
        requires_tiering=p.requires_tiering,
        has_ai_profile=p.has_ai_profile,
        has_eval_metrics=p.has_eval_metrics,
        required_intake_fields=list(p.required_intake_fields),
        synonyms=list(p.synonyms),
        note=p.note,
        used_by=(used or {}).get(p.code, 0),
    )


def project_types_out(db: Session) -> list[dto.ProjectTypeAdminOut]:
    used = _grouped_counts(db, Transition.project_type)
    return [project_type_out(p, used) for p in cfg.project_types(db, active_only=False)]


def project_type_preview(db: Session, code: str) -> dto.ProjectTypePreviewOut:
    p = cfg.project_type(db, code)
    if p is None:
        raise NotFound(f"Project type '{code}' not found")
    defs = {c.code: c for c in cfg.checklist_defs(db)}
    included = [c for c in defs.values() if c.kind == "common" or c.code in p.checklists]
    by_checklist: dict[str, int] = {}
    by_gate: dict[str, int] = {gate: 0 for gate in GATE_ORDER}
    notes: list[str] = []
    for c in included:
        rows = db.execute(
            select(PlaybookItem.gate, PlaybookItem.applies_to_project_types).where(
                PlaybookItem.active.is_(True), PlaybookItem.source == c.code
            )
        ).all()
        n = 0
        for gate, types in rows:
            if types and code not in types:
                continue
            n += 1
            by_gate[gate] = by_gate.get(gate, 0) + 1
        by_checklist[c.code] = n
        if c.tier_filtered:
            notes.append(
                f"{c.label}: items are filtered by the risk tier, so a transition gets fewer."
            )
    if any(d.kind == "portfolio_golden" for d in defs.values()):
        notes.append("The portfolio golden set of the chosen portfolio is added on top.")
    return dto.ProjectTypePreviewOut(
        code=code,
        items_by_gate={g: n for g, n in by_gate.items() if n},
        items_by_checklist=by_checklist,
        total_items=sum(by_checklist.values()),
        shows_tiering=p.requires_tiering,
        shows_ai_profile=p.has_ai_profile,
        shows_eval_metrics=p.has_eval_metrics,
        required_intake_fields=cfg.required_fields_for(db, code),
        notes=notes,
    )


# --------------------------------------------------------------------------- checklists, portfolios


def checklists_out(db: Session) -> list[dto.ChecklistAdminOut]:
    counts = _grouped_counts(db, PlaybookItem.source)
    types = cfg.project_types(db, active_only=False)
    return [
        dto.ChecklistAdminOut(
            code=c.code,
            label=c.label,
            description=c.description,
            kind=c.kind,  # type: ignore[arg-type]
            tier_filtered=c.tier_filtered,
            is_builtin=c.is_builtin,
            active=c.active,
            sort_order=c.sort_order,
            item_count=counts.get(c.code, 0),
            project_types=[p.code for p in types if c.code in p.checklists],
        )
        for c in cfg.checklist_defs(db, active_only=False)
    ]


def portfolios_out(db: Session) -> list[dto.PortfolioAdminOut]:
    used = _grouped_counts(db, Transition.portfolio)
    golden = {
        name: n
        for name, n in db.execute(
            select(PlaybookItem.portfolio, func.count())
            .where(PlaybookItem.source == "PORTFOLIO", PlaybookItem.active.is_(True))
            .group_by(PlaybookItem.portfolio)
        ).all()
    }
    return [
        dto.PortfolioAdminOut(
            name=p.name,
            code=p.code,
            label=p.label,
            description=p.description,
            focus_areas=list(p.focus_areas),
            active=p.active,
            sort_order=p.sort_order,
            requires_sites=p.requires_sites,
            sites_label=p.sites_label,
            synonyms=list(p.synonyms),
            golden_set_count=golden.get(p.name, 0),
            used_by=used.get(p.name, 0),
        )
        for p in cfg.portfolios(db, active_only=False)
    ]


# --------------------------------------------------------------------------- option lists


def option_lists_out(db: Session) -> list[dto.OptionListAdminOut]:
    lists = db.scalars(select(OptionList).order_by(OptionList.sort_order, OptionList.key)).all()
    counts: dict[str, tuple[int, int]] = {}
    for key, total, active in db.execute(
        select(
            OptionItem.list_key,
            func.count(),
            func.sum(case((OptionItem.active.is_(True), 1), else_=0)),
        ).group_by(OptionItem.list_key)
    ).all():
        counts[key] = (int(total), int(active or 0))
    return [
        dto.OptionListAdminOut(
            key=ol.key,
            label=ol.label or ol.key,
            description=ol.description,
            group=ol.group,
            is_builtin=ol.is_builtin,
            structural=ol.structural,
            lock_reason=STRUCTURAL_LOCK if ol.structural else None,
            meta_fields=[dto.MetaFieldOut(**m) for m in (ol.meta_fields or [])],
            item_count=counts.get(ol.key, (0, 0))[0],
            active_count=counts.get(ol.key, (0, 0))[1],
            sort_order=ol.sort_order,
        )
        for ol in lists
    ]


def option_list_out(db: Session, key: str) -> dto.OptionListAdminOut:
    found = next((x for x in option_lists_out(db) if x.key == key), None)
    if found is None:
        raise NotFound(f"Option list '{key}' not found")
    return found


def option_items_out(db: Session, key: str) -> dto.OptionItemsOut:
    head = option_list_out(db, key)
    used = option_usage(db, key)
    items = [
        dto.OptionItemOut(
            value=o.value,
            label=o.label,
            description=o.description,
            meta=o.meta,
            active=o.active,
            sort_order=o.sort_order,
            used_by=used.get(o.value, 0),
        )
        for o in cfg.options(db, key, active_only=False)
    ]
    return dto.OptionItemsOut(option_list=head, items=items)


# --------------------------------------------------------------------------- intake fields


def intake_fields_out(db: Session) -> list[dto.IntakeFieldAdminOut]:
    custom = custom_field_usage(db)
    out: list[dto.IntakeFieldAdminOut] = []
    for f in cfg.intake_fields(db, form=None, active_only=False):
        used = custom.get(f.key, 0)
        locked = not f.builtin and used > 0
        out.append(
            dto.IntakeFieldAdminOut(
                key=f.key,
                label=f.label,
                help=f.help,
                builtin=f.builtin,
                structural=f.structural,
                type=f.type,  # type: ignore[arg-type]
                option_list=f.option_list,
                visible=f.visible,
                required_mode=f.required_mode,  # type: ignore[arg-type]
                required_for_project_types=list(f.required_for_project_types),
                applies_to_project_types=list(f.applies_to_project_types),
                applies_to_portfolios=list(f.applies_to_portfolios),
                section=f.section,
                sort_order=f.sort_order,
                show_on_overview=f.show_on_overview,
                show_in_list=f.show_in_list,
                filterable=f.filterable,
                form=f.form,  # type: ignore[arg-type]
                min=f.min,
                max=f.max,
                max_length=f.max_length,
                active=f.active,
                used_by=used,
                type_locked=f.builtin or locked,
                lock_reason=(
                    "Built-in field: its type is fixed"
                    if f.builtin
                    else (
                        f"{used} transitions hold a value, so the type cannot change"
                        if locked
                        else None
                    )
                ),
            )
        )
    return out


# --------------------------------------------------------------------------- roles and permissions


def role_out(r: cfg.RoleCfg, users: dict[str, int]) -> dto.RoleAdminOut:
    lock = None
    if r.code == "ADMIN":
        lock = "The Admin role never holds a transition slot and keeps the admin permission"
    elif r.is_builtin:
        lock = "Built-in role: it cannot be deleted or recoded"
    return dto.RoleAdminOut(
        code=r.code,
        label=r.label,
        short_label=r.short_label,
        phrase_label=r.phrase_label,
        description=r.description,
        active=r.active,
        is_builtin=r.is_builtin,
        has_transition_slot=r.has_transition_slot,
        transition_column=r.transition_column,
        can_approve=r.can_approve,
        sort_order=r.sort_order,
        user_count=users.get(r.code, 0),
        lock_reason=lock,
    )


def roles_out(db: Session) -> list[dto.RoleAdminOut]:
    users = _grouped_counts(db, User.role)
    return [role_out(r, users) for r in cfg.roles(db, active_only=False)]


def _perm_phrase(perm: Perm, label: str) -> str:
    phrase = access.PERM_PHRASE.get(perm)
    return phrase or (label[:1].lower() + label[1:] if label else perm.value)


def generated_denial_reason(db: Session, perm: Perm, role_codes: list[str]) -> str:
    """ "Only the OR focal, PM or Architect can edit the OCET": built from the CURRENT role labels, so
    a text never names a role that lost the permission."""
    if perm is Perm.VIEW:
        return "You do not have access to Orion"
    ordered = [r.code for r in cfg.roles(db) if r.code in role_codes]
    labels = [cfg.role_phrase_label(db, c) for c in ordered]
    who = (
        "nobody"
        if not labels
        else labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} or {labels[-1]}"
    )
    text_row = db.get(PermissionText, perm.value)
    phrase = _perm_phrase(perm, text_row.label if text_row else "")
    return f"Only {who} can {phrase}"


def default_denial_text(db: Session, perm: Perm, role_codes: list[str]) -> str:
    """The 403 / tooltip text for ``perm`` when held by ``role_codes``: the original wording while the
    roles are the defaults, otherwise one generated from the current role labels."""
    if {r.value for r in MATRIX[perm]} == set(role_codes):
        return permissions.DEFAULT_DENIAL_REASONS[perm]
    return generated_denial_reason(db, perm, role_codes)


def permission_matrix_out(db: Session) -> dto.PermissionMatrixOut:
    active = cfg.roles(db)
    active_codes = [r.code for r in active]
    granted: dict[str, set[str]] = {}
    for perm, role_code in db.execute(select(RolePermission.perm, RolePermission.role_code)).all():
        granted.setdefault(perm, set()).add(role_code)
    texts = {t.perm: t for t in db.scalars(select(PermissionText)).all()}
    rows: list[dto.PermissionRowOut] = []
    for perm in Perm:
        text = texts.get(perm.value)
        roles_now = sorted(
            (c for c in granted.get(perm.value, set()) if c in active_codes), key=active_codes.index
        )
        locked: list[str] = []
        reasons: dict[str, str] = {}
        if perm is Perm.ADMIN:
            locked.append("ADMIN")
            reasons["ADMIN"] = "The Admin role always keeps the right to change configuration"
        if perm is Perm.VIEW:
            locked = list(active_codes)
            reasons = {c: "Every active role can use Orion" for c in active_codes}
        if perm in access.TRANSITION_PERMS and "ADMIN" not in locked:
            reasons.setdefault(
                "ADMIN",
                "Granting this to Admin has no effect on transitions: the Admin has no workflow override",
            )
        default_text = default_denial_text(db, perm, roles_now)
        rows.append(
            dto.PermissionRowOut(
                perm=perm.value,
                label=(text.label if text and text.label else perm.value),
                description=text.description if text else "",
                area=text.area if text else "",
                scope="transition" if perm in access.TRANSITION_PERMS else "global",
                roles=roles_now,
                denial_reason=(text.denial_reason if text and text.denial_reason else default_text),
                default_denial_reason=default_text,
                is_custom=bool(text.is_custom) if text else False,
                locked_roles=locked,
                lock_reasons=reasons,
            )
        )
    return dto.PermissionMatrixOut(
        roles=roles_out_active(db),
        permissions=rows,
        notices=[
            "Granting a transition-scoped permission also needs the person to be assigned on the transition.",
            "Orion is never a role: it has no permissions of its own (BR-050).",
        ],
    )


def roles_out_active(db: Session) -> list[dto.RoleAdminOut]:
    users = _grouped_counts(db, User.role)
    return [role_out(r, users) for r in cfg.roles(db)]


def user_out(db: Session, u: User, assigned: dict[str, int] | None = None) -> dto.UserAdminOut:
    return dto.UserAdminOut(
        id=u.id,
        name=u.name,
        email=u.email,
        role=u.role,
        role_label=cfg.role_label(db, u.role),
        focal_label=u.focal_label,
        title=u.title,
        active=bool(u.active),
        assigned_transitions=(assigned if assigned is not None else _assigned_counts(db)).get(
            u.id, 0
        ),
    )


def users_out(db: Session) -> list[dto.UserAdminOut]:
    assigned = _assigned_counts(db)
    return [user_out(db, u, assigned) for u in db.scalars(select(User).order_by(User.id))]


def _assigned_counts(db: Session) -> dict[str, int]:
    """user id -> active transitions where the person holds a slot."""
    counts: dict[str, int] = {}
    for column in access.TRANSITION_ROLE_COLUMN.values():
        attr = getattr(Transition, column)
        for uid, n in db.execute(
            select(attr, func.count())
            .where(Transition.status != "Closed", attr.is_not(None))
            .group_by(attr)
        ).all():
            counts[uid] = counts.get(uid, 0) + int(n)
    return counts


# --------------------------------------------------------------------------- tiering


def tiering_out(db: Session) -> dto.TieringConfigOut:
    return dto.TieringConfigOut(
        tiers=[dto.TierDefIn(**t) for t in cfg.tiers(db)],
        questions=[
            dto.TierQuestionOut(id=q.id, text=q.text, hint=q.hint, sort_order=q.sort_order)
            for q in cfg.tier_questions(db, active_only=False)
        ],
    )


def eval_metrics_out(db: Session) -> list[dto.EvalMetricAdminOut]:
    """All metrics (EV-nn) with their targets per tier; ``active`` is metric-level."""
    metrics: dict[str, dto.EvalMetricAdminOut] = {}
    for t in db.scalars(select(EvalTarget).order_by(EvalTarget.sort_order, EvalTarget.tier)).all():
        m = metrics.setdefault(
            t.metric_id,
            dto.EvalMetricAdminOut(
                id=t.metric_id,
                metric=t.metric,
                evaluation=t.evaluation,
                unit=t.unit,
                active=t.active,
            ),
        )
        m.targets_by_tier[str(t.tier)] = t.target_text
    return list(metrics.values())


# --------------------------------------------------------------------------- settings documents


def thresholds_out(db: Session) -> dto.ThresholdsOut:
    return dto.ThresholdsOut(
        thresholds=dto.ThresholdsDoc(**cfg.thresholds(db)), rag_rule=cfg.rag_rule_text(db)
    )


# --------------------------------------------------------------------------- templates


def templates_out(db: Session) -> list[dto.MessageTemplateAdminOut]:
    out: list[dto.MessageTemplateAdminOut] = []
    for key, (_name, d_subject, d_body, source) in cfg_defaults.DEFAULT_TEMPLATES.items():
        tpl = cfg.template(db, key)
        if tpl is None:  # cannot happen: every default key resolves
            continue
        out.append(
            dto.MessageTemplateAdminOut(
                key=key,
                name=tpl.name,
                subject=tpl.subject,
                body=tpl.body,
                enabled=tpl.enabled,
                placeholders=[dto.PlaceholderOut(**p) for p in cfg_defaults.placeholder_specs(key)],
                is_default=tpl.is_default,
                code_source=source,
                default_subject=d_subject,
                default_body=d_body,
            )
        )
    return out


SAMPLE_CONTEXT: dict[str, str] = {
    "recipient_name": "Asha Menon",
    "transition_name": "Mobility Knowledge Agent",
    "gate_short": "AtD",
    "days": "21",
    "or_focal_name": "Asha Menon",
    "item_list": '<ul><li><a href="#">S45-014</a> Prompt-injection test report (due at AtD)</li></ul>',
    "deep_link": "https://orion.example/transitions/TR-0001",
    "approver_role": "OLM",
    "verdict": "Ready with conditions",
    "orion_name": "Orion",
    "greeting": "Hi Asha Menon,",
    "sign_off": "<p>Thank you,<br>Orion, on behalf of Asha Menon</p>",
    "when": "AtD in 21 days",
    "when_suffix": " (AtD in 21 days)",
    "when_or_next_gate": "AtD in 21 days",
    "item_title": "Prompt-injection test report and 2 other items",
    "item_phrase": "these items",
    "item_count_text": "3 items",
    "open_item_count_text": "3 open items",
    "is_are": "are",
    "input_count_text": "2 inputs",
    "verdict_suffix": " (readiness: Ready with conditions)",
    "summary_html": "<p>2 conditions remain open.</p>",
    "approver_line": "<p>First approver: OLM.</p>",
    "scope": "Mobility Knowledge Agent",
    "paragraphs": "<p>Readiness is 82% with one critical gap.</p>",
    "action_title": "Close the DPIA gap",
    "due_date": "2026-11-12",
    "days_overdue_text": "4 days",
    "days_pending_text": "3 days",
    "approver_name": "Sofia Garcia",
}


def preview_template(db: Session, key: str, body: dto.TemplatePreviewIn) -> dto.TemplatePreviewOut:
    """Render a template (saved, or the unsaved edit in ``body``) with sample values."""
    tpl = cfg.template(db, key)
    if tpl is None:
        raise NotFound(f"Message template '{key}' not found")
    subject = body.subject if body.subject is not None else tpl.subject
    text = body.body if body.body is not None else tpl.body
    known = {p["name"] for p in cfg_defaults.placeholder_specs(key)}
    unknown = [n for n in cfg_defaults.placeholders_in(subject, text) if n not in known]
    values = {**SAMPLE_CONTEXT, **body.context}
    draft = cfg.TemplateCfg(
        key=key,
        name=tpl.name,
        subject=subject,
        body=text,
        enabled=tpl.enabled,
        placeholders=tuple(cfg_defaults.placeholder_specs(key)),
    )
    rendered = cfg.render_template(draft, values)
    return dto.TemplatePreviewOut(
        subject=rendered["subject"], body_html=rendered["body_html"], unknown_placeholders=unknown
    )


# --------------------------------------------------------------------------- usage


def usage(db: Session, kind: str, key: str) -> dto.UsageOut:
    """Where a value is used. ``kind``: project_type | portfolio | option (``key`` = "list:value") |
    role (users with the role) | checklist (project types listing it)."""
    if kind == "project_type":
        condition = Transition.project_type == key
    elif kind == "portfolio":
        condition = Transition.portfolio == key
    elif kind == "option":
        list_key, _, value = key.partition(":")
        column = (USAGE_COLUMNS.get(list_key) or [None])[0]
        if column is None or column.class_ is not Transition:
            count = option_usage(db, list_key).get(value, 0)
            return dto.UsageOut(kind=kind, key=key, count=count)
        condition = column == value
    elif kind == "role":
        n = db.scalar(select(func.count()).select_from(User).where(User.role == key)) or 0
        return dto.UsageOut(kind=kind, key=key, count=int(n))
    elif kind == "checklist":
        users = [p.code for p in cfg.project_types(db, active_only=False) if key in p.checklists]
        return dto.UsageOut(kind=kind, key=key, count=len(users))
    else:
        raise BadRequest(f"Unknown usage kind '{kind}'")
    total = db.scalar(select(func.count()).select_from(Transition).where(condition)) or 0
    rows = db.execute(
        select(Transition.id, Transition.name).where(condition).order_by(Transition.id).limit(10)
    ).all()
    return dto.UsageOut(
        kind=kind,
        key=key,
        count=int(total),
        transitions=[dto.UsageTransitionOut(id=i, name=n) for i, n in rows],
    )
