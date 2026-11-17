"""GET /api/v1/reference (spec §9 "Reference & users").

Public (no X-Demo-User) because the login page and forms need it before sign-in (PLAN.md A-27).
Static vocabulary comes from reference.json (stored at seed time); Admin-editable parts (flavour rules,
approval chains, portfolios, library sizes) come from their tables.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.errors import NotFound
from app.models import ApprovalChainConfig, FlavourRule, PlaybookItem, Portfolio, ReferenceData
from app.rules.constants import ACTOR_TYPES, SEVERITIES
from app.schemas.reference import (
    AppInfoOut,
    ChecklistCountsOut,
    EnumsOut,
    PortfolioDetailOut,
    ProjectTypeOut,
    ReferenceOut,
)

router = APIRouter(tags=["reference"])

ENUMS = EnumsOut(
    severities=list(SEVERITIES),
    evidence_types=["Document", "Link", "Email sign-off", "Recording", "Generated"],
    evidence_statuses=["Submitted", "Accepted", "Rejected"],
    action_statuses=["Open", "In progress", "Done", "Cancelled"],
    action_priorities=["High", "Medium", "Low"],
    condition_statuses=["Open", "Closed"],
    exception_statuses=["Draft", "Pending CISO/BISO", "Approved", "Rejected"],
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


@router.get("/reference", response_model=ReferenceOut)
def get_reference(db: Session = Depends(get_db)) -> ReferenceOut:
    row = db.get(ReferenceData, "reference")
    if row is None:
        raise NotFound("Reference data not loaded – reset the demo data")
    ref: dict[str, Any] = row.data
    settings = get_settings()

    project_types = [
        ProjectTypeOut(
            code=fr.project_type,
            checklists=list(fr.checklists),
            requires_tiering=fr.requires_tiering,
            note=fr.note,
        )
        for fr in db.scalars(select(FlavourRule)).all()
    ]
    order = {code: i for i, code in enumerate(p["code"] for p in ref["project_types"])}
    project_types.sort(key=lambda p: order.get(p.code, 99))

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
    portfolio_order = {name: i for i, name in enumerate(ref["portfolios"])}
    portfolios = sorted(
        db.scalars(select(Portfolio)).all(), key=lambda p: portfolio_order.get(p.name, 99)
    )
    portfolio_details = [
        PortfolioDetailOut(
            name=p.name,
            code=p.code,
            focus_areas=list(p.focus_areas),
            intake_extra_fields=p.intake_extra_fields or [],
            golden_set_count=golden_counts.get(p.name, 0),
            golden_set_mandatory_count=mandatory_counts.get(p.name, 0),
        )
        for p in portfolios
    ]

    chains = {c.type: c.steps for c in db.scalars(select(ApprovalChainConfig)).all()}

    return ReferenceOut(
        gates=ref["gates"],
        gate_outcomes=ref["gate_outcomes"],
        lenses=ref["lenses"],
        item_statuses=ref["item_statuses"],
        done_statuses=ref["done_statuses"],
        na_statuses=ref["na_statuses"],
        gap_statuses=ref["gap_statuses"],
        design_effectiveness_options=ref["design_effectiveness_options"],
        project_types=project_types,
        flavour_rule_note=ref.get("flavour_rule_note", ""),
        portfolios=[p.name for p in portfolios],
        portfolio_details=portfolio_details,
        regions=ref["regions"],
        intake_options=ref["intake_options"],
        tiers=ref["tiers"],
        tier_dimensions=ref["tier_dimensions"],
        tier_questions=ref["tier_questions"],
        rag_rule=ref["rag_rule"],
        approval_chains=chains,
        risk_acceptance_routes=ref.get("risk_acceptance_routes", []),
        risk_acceptance_then=ref.get("risk_acceptance_then", []),
        ocet=ref["ocet"],
        roles=ref["roles"],
        checklist_counts=_checklist_counts(db),
        enums=ENUMS,
        app=AppInfoOut(
            demo_mode=settings.demo_mode,
            ai_mode=settings.ai_mode,
            mail_mode=settings.mail_mode,
            orion_mailbox=settings.orion_mailbox,
        ),
    )
