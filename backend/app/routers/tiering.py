"""Tiering and AI profile: /tiering/propose, /transitions/{id}/tier, /tier/confirm, /ai-profile (FR-021, BR-011). M3."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.tiering import (
    AIProfileIn,
    AIProfileOut,
    TierAssessmentOut,
    TierConfirmIn,
    TierProposalOut,
    TierProposeIn,
    TierSetIn,
)

router = APIRouter(tags=["tiering"], dependencies=[Depends(get_current_user)])


@router.post("/tiering/propose", response_model=TierProposalOut)
def propose_tier(
    body: TierProposeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TierProposalOut:
    """Pure BR-011 rule (spec §7.2), no persistence; used live by the wizard. Any signed-in role.

    Evaluated in order: TQ2 or TQ3 yes or sensitive_data "SOX / MC" -> Tier 4; TQ1 yes or audience
    "External" or sensitive_data "Personal sensitive" or write_actions "Yes" -> Tier 3; TQ5 yes ->
    Tier 1; TQ4 yes -> Tier 2; else Tier 3. Rationale lists the facts that applied ("Internal
    audience", "No write actions", "TQ4 = yes -> Tier 2"). ``tier`` is the definition card from
    the configured tier definitions, ``dimensions`` the tier dimensions. 422 when an answers key is not
    a tiering question or an intake value is not an option. The question wording and tier definitions
    are configuration (Admin: Rules & thresholds); the rule itself is fixed.
    """
    from app.domain import tiering as tiering_domain

    return tiering_domain.propose(db, body)


@router.put("/transitions/{transition_id}/tier", response_model=TierAssessmentOut)
def propose_transition_tier(
    transition_id: str,
    body: TierSetIn,
    user: User = Depends(require(Perm.PROPOSE_TIER)),
    db: Session = Depends(get_db),
) -> TierAssessmentOut:
    """OR focal proposes the tier. The server computes the proposal (BR-011) from the transition's
    audience / write_actions / sensitive_data and ``body.answers``; client-supplied tiers are not
    accepted.

    403 without PROPOSE_TIER; 404 unknown id; 409 "Tiering applies to AI project types only" when the
    project type does not require tiering; 409 "Tier already confirmed – IRM must change it" when the
    tier is already Confirmed (the OR focal may not overwrite a confirmed tier).
    Upserts TierAssessment (answers, proposed_tier, rationale, proposed_by = user), sets
    Transition.risk_tier = proposed and tier_status "Proposed". If the assessment is already launched
    re-assemble (BR-010 step 7) with the new proposed tier and put counts in ``reassembly``.
    Audit Human "Tier proposed".
    """
    from app.domain import tiering as tiering_domain
    from app.domain.intake import get_transition

    t = get_transition(db, transition_id)
    out = tiering_domain.set_proposal(db, user, t, body.answers)
    db.commit()
    return out


@router.post("/transitions/{transition_id}/tier/confirm", response_model=TierAssessmentOut)
def confirm_transition_tier(
    transition_id: str,
    body: TierConfirmIn,
    user: User = Depends(require(Perm.CONFIRM_TIER)),
    db: Session = Depends(get_db),
) -> TierAssessmentOut:
    """IRM confirms the proposed tier or changes it ("Change tier"). Orion never does this.

    403 without CONFIRM_TIER (IRM only); 404 unknown id; 409 "No tier proposed yet" when no proposal
    exists; 422 "Reason required to change the tier" when body.tier differs from the proposal and
    ``reason`` is blank. Sets confirmed_tier, confirmed_by_irm = user, confirmed_by_or_focal = the
    proposer, confirmed_at = now (app clock), change_reason (only when changed),
    Transition.risk_tier = confirmed and tier_status "Confirmed". If the assessment is launched and
    the tier changed versus the tier currently applied, re-assemble (BR-010 step 7) and return counts
    in ``reassembly``. Audit Human "Tier confirmed" / "Tier changed" with the reason.
    """
    from app.domain import tiering as tiering_domain
    from app.domain.intake import get_transition

    t = get_transition(db, transition_id)
    out = tiering_domain.confirm(db, user, t, body)
    db.commit()
    return out


@router.get("/transitions/{transition_id}/ai-profile", response_model=AIProfileOut)
def get_ai_profile(
    transition_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIProfileOut:
    """AI profile questionnaire (spec §8.5 step 3). 404 unknown id; 409 "AI profile applies to AI
    project types only" when the project type's "Has AI profile" switch is off. Returns empty defaults when none was saved yet.
    """
    from app.domain import tiering as tiering_domain
    from app.domain.intake import get_transition

    t = get_transition(db, transition_id)
    tiering_domain.require_ai_profile(db, t, "AI profile applies to AI project types only")
    return tiering_domain.profile_out(db, t)


@router.put("/transitions/{transition_id}/ai-profile", response_model=AIProfileOut)
def put_ai_profile(
    transition_id: str,
    body: AIProfileIn,
    user: User = Depends(require(Perm.EDIT_AI_PROFILE)),
    db: Session = Depends(get_db),
) -> AIProfileOut:
    """Replace the AI profile (upsert). 403 without EDIT_AI_PROFILE; 404 unknown id; 409 when the project
    type has no AI profile. Audit Human "AI profile updated"."""
    from app.domain import tiering as tiering_domain
    from app.domain.intake import get_transition

    t = get_transition(db, transition_id)
    out = tiering_domain.save_profile(db, user, t, body)
    db.commit()
    return out
