"""Transition detail assembly (spec §8.7 header). Other areas call this after mutations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transition, User
from app.rules.constants import GATE_ORDER, GATE_SHORT, GATE_TYPE, GATES, LENSES
from app.schemas.common import PersonRef
from app.schemas.intake import (
    GateStepOut,
    ItemCountsOut,
    LensCardOut,
    RolesOut,
    SiteOut,
    TierInfoOut,
    TransitionDetailOut,
)

# Reference role code -> short label for the lens "owner" line.
_ROLE_LABELS = {
    "OR_FOCAL": "OR focal",
    "PM": "PM",
    "ARCHITECT": "Architect",
    "OLM": "OLM",
    "IRM": "IRM",
    "PLANNER": "Planner",
}


def build_transition_detail(
    db: Session, transition: Transition, user: User | None = None
) -> TransitionDetailOut:
    """Full detail DTO for ``transition`` (summary fields come from ``metrics.to_summary``).

    With ``user`` the DTO also carries ``access``: what this user may do on this transition
    (``app.access.access_map``), so the UI can disable controls with the reason (spec 12)."""
    from app.access import access_map
    from app.domain import scope as scope_domain
    from app.domain.metrics import compute_metrics, to_summary
    from app.domain.tiering import reference

    t = transition
    metrics = compute_metrics(db, [t])[0]
    summary = to_summary(metrics)
    ref = reference(db)
    users = {u.id: u for u in db.scalars(select(User))}

    def person(user_id: str | None) -> PersonRef | None:
        if not user_id:
            return None
        user = users.get(user_id)
        return PersonRef(id=user_id, name=user.name if user else "")

    requires = scope_domain.requires_tiering(db, t.project_type)
    launched = t.assessment_launched_at is not None

    assessment = scope_domain.get_assessment(db, t.id)
    tier_info: TierInfoOut | None = None
    if assessment is not None:
        status = (
            "Confirmed"
            if assessment.confirmed_tier is not None
            else ("Proposed" if assessment.proposed_tier is not None else None)
        )
        tier_info = TierInfoOut(
            proposed_tier=assessment.proposed_tier,
            confirmed_tier=assessment.confirmed_tier,
            status=status,
            rationale=list(assessment.rationale or []),
            proposed_by=person(assessment.proposed_by),
            confirmed_by_or_focal=person(assessment.confirmed_by_or_focal),
            confirmed_by_irm=person(assessment.confirmed_by_irm),
            confirmed_at=assessment.confirmed_at,
            change_reason=assessment.change_reason,
            answers=dict(assessment.answers or {}),
        )

    banner: str | None = None
    if requires and launched and t.tier_status == "Proposed" and t.risk_tier is not None:
        banner = f"Checklist based on proposed Tier {t.risk_tier} — confirm tier to finalise"

    item_counts: ItemCountsOut | None = None
    if launched:
        counts = scope_domain.stored_counts(scope_domain.stored_items(db, t.id))
        item_counts = ItemCountsOut(
            framework=counts["framework"],
            ai_applicable=counts["ai_applicable"],
            ai_excluded=counts["ai_excluded"],
            golden_set_applies=counts["golden_set_applies"],
            golden_set_to_confirm=counts["golden_set_to_confirm"],
            common=counts["common"],
            total=counts["total_applicable"],
        )

    lens_ref = {row["code"]: row for row in ref.get("lenses", [])}
    lenses: list[LensCardOut] = []
    for lens in LENSES:
        r = metrics.readiness.lenses[lens]
        info = lens_ref.get(lens, {})
        lenses.append(
            LensCardOut(
                lens=lens,
                question=info.get("question", ""),
                owner_label=" / ".join(
                    _ROLE_LABELS.get(code, code) for code in info.get("owner_roles", [])
                ),
                scope=r.scope,
                done=r.done,
                in_progress=r.in_progress,
                not_started=r.not_started,
                open_gaps=r.open_gaps,
                critical_gaps=r.critical_gaps,
                readiness_pct=r.readiness_pct,
            )
        )

    gate_labels = {g["code"]: g.get("label", g["code"]) for g in ref.get("gates", [])}
    current_order = GATE_ORDER[t.current_gate]
    gates = [
        GateStepOut(
            code=code,
            short=GATE_SHORT[code],
            label=gate_labels.get(code, code),
            type=GATE_TYPE[code],
            state=(
                "done"
                if GATE_ORDER[code] < current_order
                else "current" if code == t.current_gate else "upcoming"
            ),
        )
        for code in GATES
    ]

    return TransitionDetailOut(
        **summary.model_dump(),
        servicenow_project_id=t.servicenow_project_id,
        description=t.description or "",
        investment_type=t.investment_type,
        delivery_method=t.delivery_method,
        audience=t.audience,
        write_actions=t.write_actions,
        sensitive_data=t.sensitive_data,
        target_gate=t.target_gate,
        sites=[
            SiteOut(site_id=s.get("site_id", ""), site_key=s.get("site_key", ""))
            for s in (t.sites or [])
        ],
        roles=RolesOut(
            or_focal=person(t.or_focal_user_id),
            pm=person(t.pm_user_id),
            architect=person(t.architect_user_id),
            olm=person(t.olm_user_id),
            irm=person(t.irm_user_id),
        ),
        flavour_label=f"{t.project_type} · {t.portfolio} · {t.region}",
        requires_tiering=requires,
        tier=tier_info,
        checklist_banner=banner,
        item_counts=item_counts,
        lenses=lenses,
        gates=gates,
        hypercare_no_defects_confirmed=bool(t.hypercare_no_defects_confirmed),
        created_at=t.created_at,
        created_by=person(t.created_by),
        access=access_map(db, user, t) if user is not None else {},
    )
