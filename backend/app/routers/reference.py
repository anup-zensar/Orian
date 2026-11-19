"""GET /api/v1/reference (spec §9 "Reference & users").

Public (no X-Demo-User) because the login page and forms need it before sign-in (PLAN.md A-27):
it never contains users or message templates.

Structural vocabulary (statuses, gate codes / order / outcomes, item status buckets) comes from
reference.json (stored at seed time). Everything an Admin can edit (CR-01) comes from the
configuration tables through ``app.domain.cfg``: project types, portfolios, option lists, roles, tier
questions, thresholds. Every key that existed before CR-01 keeps its shape.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.domain import cfg
from app.domain.approvals import pending_exception_statuses
from app.errors import NotFound
from app.models import ApprovalChainConfig, PlaybookItem, ReferenceData
from app.rules.constants import ACTOR_TYPES, SEVERITIES
from app.schemas.reference import (
    AppInfoOut,
    ChecklistCountsOut,
    ChecklistRefOut,
    EnumsOut,
    IntakeFieldRefOut,
    OptionOut,
    PortfolioDetailOut,
    ProjectTypeOut,
    ReferenceOut,
    RoleOut,
)

router = APIRouter(tags=["reference"])

# DEFAULT vocabularies (used before seeding and by nl_intake); GET /reference derives the live ones
# from the option lists (``_enums``).
ENUMS = EnumsOut(
    severities=list(SEVERITIES),
    evidence_types=["Document", "Link", "Email sign-off", "Recording", "Generated"],
    evidence_statuses=["Submitted", "Accepted", "Rejected"],
    action_statuses=["Open", "In progress", "Done", "Cancelled"],
    action_priorities=["High", "Medium", "Low"],
    condition_statuses=["Open", "Closed"],
    exception_statuses=[
        "Draft",
        "Pending IRM",
        "Pending CISO/BISO",
        "Approved",
        "Rejected",
    ],  # default; computed per request
    risk_ratings=["High", "Medium", "Low"],
    defect_priorities=["P1", "P2", "P3", "P4"],
    defect_statuses=["Open", "Resolved"],
    actor_types=list(ACTOR_TYPES),
    draft_kinds=["Reminder", "Chaser", "Input request", "Approval request", "Leadership update"],
    approval_types=["OCET", "AtD", "AtO", "SUPPORT_MODEL", "EXCEPTION", "RISK_ACCEPTANCE"],
    applicability=["Applies", "Not applicable", "To confirm"],
    item_sources=["FRAMEWORK", "AI_PLAYBOOK", "PORTFOLIO", "COMMON"],
)


def _checklist_counts(db: Session) -> ChecklistCountsOut:
    def count(*conditions: Any) -> int:
        return db.scalar(select(func.count()).select_from(PlaybookItem).where(*conditions)) or 0

    active = PlaybookItem.active.is_(True)
    ai_items = db.scalars(
        select(PlaybookItem.applicable_tiers).where(active, PlaybookItem.source == "AI_PLAYBOOK")
    ).all()
    by_tier = {str(t): sum(1 for tiers in ai_items if t in (tiers or [])) for t in (1, 2, 3, 4)}
    return ChecklistCountsOut(
        framework=count(active, PlaybookItem.source == "FRAMEWORK"),
        ai_playbook_total=len(ai_items),
        ai_playbook_by_tier=by_tier,
        common=count(active, PlaybookItem.source == "COMMON"),
    )


def _active_option_values(db: Session, key: str, fallback: list[str]) -> list[str]:
    values = cfg.option_values(db, key)
    return values if values or cfg.option_list_exists(db, key) else list(fallback)


def _enums(db: Session, exception_statuses: list[str]) -> EnumsOut:
    """The small vocabularies, taken from the option lists (active values) with code defaults."""

    def values(key: str, default: list[str]) -> list[str]:
        return _active_option_values(db, key, default)

    return EnumsOut(
        severities=values("severities", ENUMS.severities),
        evidence_types=values("evidence_types", ENUMS.evidence_types),
        evidence_statuses=values("evidence_statuses", ENUMS.evidence_statuses),
        action_statuses=values("action_statuses", ENUMS.action_statuses),
        action_priorities=values("action_priorities", ENUMS.action_priorities),
        condition_statuses=values("condition_statuses", ENUMS.condition_statuses),
        exception_statuses=exception_statuses,
        risk_ratings=values("risk_ratings", ENUMS.risk_ratings),
        defect_priorities=values("defect_priorities", ENUMS.defect_priorities),
        defect_statuses=values("defect_statuses", ENUMS.defect_statuses),
        actor_types=values("actor_types", ENUMS.actor_types),
        draft_kinds=values("draft_kinds", ENUMS.draft_kinds),
        approval_types=values("approval_types", ENUMS.approval_types),
        applicability=values("applicability", ENUMS.applicability),
        item_sources=[c.code for c in cfg.checklist_defs(db)] or ENUMS.item_sources,
    )


def _ocet(db: Session, base: dict[str, Any]) -> dict[str, Any]:
    """OCET config: categories, pricing, currencies, growth from the lists; statuses from reference.json."""
    t = cfg.thresholds(db)
    categories = cfg.options(db, "ocet_categories")
    out = dict(base)
    out["categories"] = [o.value for o in categories] or base.get("categories", [])
    out["pricing_basis"] = cfg.option_values(db, "ocet_pricing_basis") or base.get(
        "pricing_basis", []
    )
    out["currencies"] = cfg.option_values(db, "ocet_currencies") or base.get("currencies", [])
    out["default_horizon_years"] = t["default_horizon_years"]
    if categories:
        out["default_growth_pct"] = {
            o.value: o.meta.get("default_growth_pct", t["default_growth_pct"]) for o in categories
        }
    return out


@router.get("/reference", response_model=ReferenceOut)
def get_reference(
    include_inactive: bool = Query(
        default=False,
        description="Also return inactive project types, portfolios, list values, roles and fields "
        "(each carries `active`); the UI filters them itself",
    ),
    db: Session = Depends(get_db),
) -> ReferenceOut:
    row = db.get(ReferenceData, "reference")
    if row is None:
        raise NotFound("Reference data not loaded – reset the demo data")
    ref: dict[str, Any] = row.data
    settings = get_settings()
    active_only = not include_inactive

    project_types = [
        ProjectTypeOut(
            code=p.code,
            checklists=list(p.checklists),
            requires_tiering=p.requires_tiering,
            note=p.note,
            label=p.label,
            description=p.description,
            active=p.active,
            sort_order=p.sort_order,
            has_ai_profile=p.has_ai_profile,
            has_eval_metrics=p.has_eval_metrics,
            required_intake_fields=list(p.required_intake_fields),
            synonyms=list(p.synonyms),
        )
        for p in cfg.project_types(db, active_only=active_only)
    ]

    golden_counts = {
        name: n
        for name, n in db.execute(
            select(PlaybookItem.portfolio, func.count())
            .where(PlaybookItem.source == "PORTFOLIO", PlaybookItem.active.is_(True))
            .group_by(PlaybookItem.portfolio)
        ).all()
    }
    mandatory_counts = {
        name: n
        for name, n in db.execute(
            select(PlaybookItem.portfolio, func.count())
            .where(
                PlaybookItem.source == "PORTFOLIO",
                PlaybookItem.active.is_(True),
                PlaybookItem.mandatory.is_(True),
            )
            .group_by(PlaybookItem.portfolio)
        ).all()
    }
    portfolio_details = [
        PortfolioDetailOut(
            name=p.name,
            code=p.code,
            focus_areas=list(p.focus_areas),
            intake_extra_fields=[],
            golden_set_count=golden_counts.get(p.name, 0),
            golden_set_mandatory_count=mandatory_counts.get(p.name, 0),
            label=p.label,
            description=p.description,
            requires_sites=p.requires_sites,
            sites_label=p.sites_label,
            synonyms=list(p.synonyms),
            active=p.active,
            sort_order=p.sort_order,
        )
        for p in cfg.portfolios(db, active_only=active_only)
    ]

    chain_rows = db.scalars(select(ApprovalChainConfig)).all()
    chains = {c.type: c.steps for c in chain_rows}
    chain_labels = {c.type: c.label for c in chain_rows if c.label}

    lists = {
        key: [
            OptionOut(
                value=o.value,
                label=o.label,
                description=o.description,
                meta=o.meta,
                active=o.active,
            )
            for o in cfg.options(db, key, active_only=active_only)
        ]
        for key in cfg.option_list_keys(db)
    }
    intake_options = {
        key: cfg.option_values(db, key) for key in cfg.option_list_keys(db, group="Intake")
    }
    routes = [
        {"gap_category": o.value, "endorsement": str(o.meta.get("endorsement", ""))}
        for o in cfg.options(db, "risk_gap_categories")
    ]
    t = cfg.thresholds(db)
    roles = [
        RoleOut(
            code=r.code,
            label=r.label,
            short_label=r.short_label,
            phrase_label=r.phrase_label,
            active=r.active,
            is_builtin=r.is_builtin,
            has_transition_slot=r.has_transition_slot,
            transition_column=r.transition_column,
            can_approve=r.can_approve,
            sort_order=r.sort_order,
        )
        for r in cfg.roles(db, active_only=active_only)
    ]

    return ReferenceOut(
        gates=ref["gates"],
        gate_outcomes=ref["gate_outcomes"],
        lenses=ref["lenses"],
        item_statuses=ref["item_statuses"],
        done_statuses=ref["done_statuses"],
        na_statuses=ref["na_statuses"],
        gap_statuses=ref["gap_statuses"],
        design_effectiveness_options=cfg.option_values(db, "design_effectiveness")
        or ref["design_effectiveness_options"],
        project_types=project_types,
        flavour_rule_note=ref.get("flavour_rule_note", ""),
        portfolios=[p.name for p in cfg.portfolios(db)],
        portfolio_details=portfolio_details,
        regions=cfg.option_values(db, "regions") or ref["regions"],
        intake_options=intake_options or ref["intake_options"],
        tiers=cfg.tiers(db),
        tier_dimensions=cfg.tier_dimensions(db),
        tier_questions=[
            {"id": q.id, "text": q.text, "if_yes": q.hint} for q in cfg.tier_questions(db)
        ],
        rag_rule=cfg.rag_rule_text(db),
        approval_chains=chains,
        risk_acceptance_routes=routes or ref.get("risk_acceptance_routes", []),
        risk_acceptance_then=cfg.option_values(db, "risk_acceptance_then")
        or ref.get("risk_acceptance_then", []),
        ocet=_ocet(db, ref["ocet"]),
        roles=roles,
        checklist_counts=_checklist_counts(db),
        enums=_enums(
            db,
            # "Pending <role>" per step of the configured EXCEPTION chain (EX-status)
            ["Draft", *pending_exception_statuses(db), "Approved", "Rejected"],
        ),
        app=AppInfoOut(
            demo_mode=settings.demo_mode,
            ai_mode=settings.ai_mode,
            mail_mode=settings.mail_mode,
            orion_mailbox=settings.orion_mailbox,
        ),
        lists=lists,
        intake_fields=[
            IntakeFieldRefOut(
                **{k: (list(v) if isinstance(v, tuple) else v) for k, v in vars(f).items()}
            )
            for f in cfg.intake_fields(db, form=None, active_only=active_only)
        ],
        checklists=[
            ChecklistRefOut(
                code=c.code,
                label=c.label,
                description=c.description,
                kind=c.kind,
                tier_filtered=c.tier_filtered,
                is_builtin=c.is_builtin,
                active=c.active,
                sort_order=c.sort_order,
            )
            for c in cfg.checklist_defs(db, active_only=active_only)
        ],
        thresholds={
            "rag": t["rag"],
            "insights": t["insights"],
            "calendar_horizon_days": t["calendar_horizon_days"],
            "leadership_decision_window_days": t["leadership_decision_window_days"],
            "default_tier": t["default_tier"],
            "narrative_top": t["narrative_top"],
        },
        approval_chain_labels=chain_labels,
    )
