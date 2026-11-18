"""Scope and launch: /transitions/{id}/scope, /launch-assessment (FR-022, BR-010). M3."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.scope import LaunchOut, ScopeOut, ScopeUpdateIn

router = APIRouter(tags=["scope"], dependencies=[Depends(get_current_user)])


@router.get("/transitions/{transition_id}/scope", response_model=ScopeOut)
def get_scope(
    transition_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScopeOut:
    """Portfolio scope page data (spec §8.6). 404 unknown id.

    ``golden_set``: the portfolio's active PORTFOLIO library items (type "Mandatory" when mandatory,
    else "Portfolio"); ``common``: COMMON items (type "Common"). Each row: id, requirement (title),
    gate / gate_short, owner_hint, lens, lens_is_suggested, ``applies`` and ``locked``
    (mandatory -> locked, always "Yes"). ``applies`` source: after launch the TransitionItem
    applicability (Applies -> Yes, Not applicable -> No, To confirm); before launch Transition.scope_
    decisions, falling back to the BR-010 default (mandatory / always -> Yes, else To confirm).
    ``reason`` from the decision / na_reason.
    ``counts`` {framework, ai_applicable, ai_excluded, golden_set_applies, golden_set_to_confirm,
    common, total}: from stored items after launch, else from ``assemble_checklist`` with the
    confirmed or proposed tier (None tier -> all AI items apply) with scope_decisions applied; total =
    applicable items. ``tier_banner`` only for AI flavours: {tier, status, text} where text is
    "Checklist based on proposed Tier N — confirm tier to finalise" when Proposed,
    "Checklist based on confirmed Tier N" when Confirmed, "Tier not proposed yet" when none.
    ``recommendations``: for rows still "To confirm" only, from
    ``AIService.recommend_applicability(items, flavour)`` (Orion agent, advisory, never persisted).
    ``launched`` = assessment_launched_at is set. Any signed-in role.
    """
    from app.domain import scope as scope_domain
    from app.domain.intake import get_transition

    return scope_domain.build_scope(db, get_transition(db, transition_id))


@router.put("/transitions/{transition_id}/scope", response_model=ScopeOut)
def update_scope(
    transition_id: str,
    body: ScopeUpdateIn,
    user: User = Depends(require(Perm.CONFIRM_SCOPE)),
    db: Session = Depends(get_db),
) -> ScopeOut:
    """Record applicability decisions (OR focal). 403 without CONFIRM_SCOPE; 404 unknown id.

    422 when an item_id is not a golden-set / common row of this transition's portfolio. 409 (with a
    reason per row) when a decision sets a locked (mandatory / always) row to "No" or "To confirm".
    Before launch decisions are stored in Transition.scope_decisions ({item_id: {applies, reason}});
    after launch they are applied to TransitionItem: Yes -> Applies, No -> Not applicable with
    na_reason = reason (excluded_by None, lens N/A status via na_status_for), To confirm ->
    To confirm. After launch "No" needs a reason (422) and is refused (409, reasons) for items that
    already have evidence or a done status; one audit event per changed item (before/after).
    403 unless the user is the OR focal assigned to THIS transition.
    Audit Human with counts; note "Accepted Orion recommendations" when source is
    "orion_recommendation" (the UI sends the recommended values; the server still validates each
    row). Returns the refreshed ScopeOut.
    """
    from app.domain import scope as scope_domain
    from app.domain.intake import get_transition

    t = get_transition(db, transition_id)
    scope_domain.update_scope(db, user, t, body)
    db.commit()
    return scope_domain.build_scope(db, t)


@router.post("/transitions/{transition_id}/launch-assessment", response_model=LaunchOut)
def launch_assessment(
    transition_id: str,
    user: User = Depends(require(Perm.CONFIRM_SCOPE)),
    db: Session = Depends(get_db),
) -> LaunchOut:
    """Launch the readiness assessment (FR-022, BR-010). 403 without CONFIRM_SCOPE; 404 unknown id.

    409 with reasons: "Assessment already launched"; "Propose a tier before launching" when the flavour
    requires tiering and no tier is proposed. Creates TransitionItems from
    ``assemble_checklist(library, project_type, portfolio, tier, flavour checklists, roles)`` using the
    confirmed tier, else the proposed one; applies Transition.scope_decisions (Yes -> Applies, No ->
    Not applicable with na_reason, status via na_status_for; excluded_by None); owners per BR-010
    step 6; sets assessment_launched_at (app clock). Audit Human "Assessment launched" with counts.
    Returns {transition_id, counts (summarize_counts), redirect "/transitions/<id>/assessment"}.
    """
    from app.domain import scope as scope_domain
    from app.domain.intake import get_transition

    t = get_transition(db, transition_id)
    out = scope_domain.launch_assessment(db, user, t)
    db.commit()
    return out
