"""Tier proposal / confirmation and the AI profile (BR-011, FR-021; spec 8.5)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.access import ensure_transition_role
from app.domain import audit
from app.domain import scope as scope_domain
from app.errors import BadRequest, Conflict
from app.models import AIProfile, ReferenceData, TierAssessment, Transition, User
from app.permissions import Perm
from app.rules.constants import ACTOR_HUMAN
from app.rules.tiering import propose_tier, unknown_question_ids
from app.schemas.common import PersonRef
from app.schemas.tiering import (
    AIProfileIn,
    AIProfileOut,
    TierAssessmentOut,
    TierCardOut,
    TierConfirmIn,
    TierProposalOut,
    TierProposeIn,
)

TIER_FIELDS = ("proposed_tier", "confirmed_tier", "rationale", "answers", "change_reason")
AI_PROFILE_FIELDS = (
    "infrastructure_solution",
    "agentic_framework",
    "multi_agent_orchestration",
    "number_of_users",
    "agentic_workflows",
    "models_used",
    "data_sources",
    "hosting",
    "write_actions_detail",
)


# --- reference -----------------------------------------------------------------------------------


def reference(db: Session) -> dict[str, Any]:
    row = db.get(ReferenceData, "reference")
    return dict(row.data) if row is not None and row.data else {}


def tier_card(db: Session, tier: int | None) -> TierCardOut | None:
    if tier is None:
        return None
    for card in reference(db).get("tiers", []):
        if card.get("tier") == tier:
            return TierCardOut(
                tier=card["tier"],
                name=card.get("name", ""),
                definition=card.get("definition", ""),
                examples=card.get("examples", ""),
                builder_persona=card.get("builder_persona", ""),
            )
    return None


def tier_dimensions(db: Session) -> list[str]:
    return list(reference(db).get("tier_dimensions", []))


def validate_inputs(
    db: Session,
    audience: str | None,
    write_actions: str | None,
    sensitive_data: str | None,
    answers: dict[str, bool],
) -> None:
    """422 when an answers key is not TQ1..TQ5 or an intake value is not a reference option."""
    options = reference(db).get("intake_options", {})
    reasons = [f"Unknown tier question '{k}' (use TQ1..TQ5)" for k in unknown_question_ids(answers)]
    for field, value in (
        ("audience", audience),
        ("write_actions", write_actions),
        ("sensitive_data", sensitive_data),
    ):
        allowed = options.get(field, [])
        if value is not None and allowed and value not in allowed:
            reasons.append(f"{field} '{value}' is not one of: {', '.join(allowed)}")
    if reasons:
        raise BadRequest("Validation failed", reasons)


# --- propose -------------------------------------------------------------------------------------


def propose(db: Session, body: TierProposeIn) -> TierProposalOut:
    validate_inputs(db, body.audience, body.write_actions, body.sensitive_data, body.answers)
    result = propose_tier(body.audience, body.write_actions, body.sensitive_data, body.answers)
    card = tier_card(db, result.tier)
    if card is None:
        card = TierCardOut(
            tier=result.tier,
            name=f"Tier {result.tier}",
            definition="",
            examples="",
            builder_persona="",
        )
    return TierProposalOut(
        proposed_tier=result.tier,
        rationale=result.rationale,
        tier=card,
        dimensions=tier_dimensions(db),
    )


def _person(db: Session, user_id: str | None) -> PersonRef | None:
    if not user_id:
        return None
    user = db.get(User, user_id)
    return PersonRef(id=user_id, name=user.name if user else "") if user_id else None


def assessment_out(
    db: Session,
    t: Transition,
    assessment: TierAssessment | None,
    reassembly: dict[str, int] | None = None,
) -> TierAssessmentOut:
    if assessment is None:
        return TierAssessmentOut(
            transition_id=t.id,
            answers={},
            proposed_tier=None,
            confirmed_tier=None,
            status=None,
            rationale=[],
            proposed_by=None,
            confirmed_by_or_focal=None,
            confirmed_by_irm=None,
            confirmed_at=None,
            change_reason=None,
            tier=None,
            dimensions=tier_dimensions(db),
            reassembly=reassembly,
        )
    status = (
        "Confirmed"
        if assessment.confirmed_tier is not None
        else ("Proposed" if assessment.proposed_tier is not None else None)
    )
    shown = assessment.confirmed_tier or assessment.proposed_tier
    return TierAssessmentOut(
        transition_id=t.id,
        answers=dict(assessment.answers or {}),
        proposed_tier=assessment.proposed_tier,
        confirmed_tier=assessment.confirmed_tier,
        status=status,
        rationale=list(assessment.rationale or []),
        proposed_by=_person(db, assessment.proposed_by),
        confirmed_by_or_focal=_person(db, assessment.confirmed_by_or_focal),
        confirmed_by_irm=_person(db, assessment.confirmed_by_irm),
        confirmed_at=assessment.confirmed_at,
        change_reason=assessment.change_reason,
        tier=tier_card(db, shown),
        dimensions=tier_dimensions(db),
        reassembly=reassembly,
    )


def require_ai_flavour(db: Session, t: Transition, message: str) -> None:
    if not scope_domain.requires_tiering(db, t.project_type):
        raise Conflict(message)


def set_proposal(
    db: Session, user: User, t: Transition, answers: dict[str, bool]
) -> TierAssessmentOut:
    """OR focal proposes the tier; the server computes it (caller commits)."""
    ensure_transition_role(db, user, t, Perm.PROPOSE_TIER)
    require_ai_flavour(db, t, "Tiering applies to AI project types only")
    assessment = scope_domain.get_assessment(db, t.id)
    if assessment is not None and assessment.confirmed_tier is not None:
        raise Conflict("Tier already confirmed – IRM must change it")
    validate_inputs(db, t.audience, t.write_actions, t.sensitive_data, answers)
    result = propose_tier(t.audience, t.write_actions, t.sensitive_data, answers)

    before = audit.snapshot(assessment, TIER_FIELDS) if assessment is not None else None
    if assessment is None:
        assessment = TierAssessment(transition_id=t.id)
        db.add(assessment)
    assessment.answers = {k: bool(v) for k, v in answers.items()}
    assessment.proposed_tier = result.tier
    assessment.rationale = result.rationale
    assessment.proposed_by = user.id
    t.risk_tier = result.tier
    t.tier_status = "Proposed"
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="TierAssessment",
        entity_id=t.id,
        action="Tier proposed",
        transition_id=t.id,
        before=before,
        after=audit.snapshot(assessment, TIER_FIELDS),
        note=f"Proposed Tier {result.tier}",
    )
    reassembly = None
    if t.assessment_launched_at is not None:
        reassembly = scope_domain.reassemble_transition(
            db,
            t,
            user,
            action="Checklist re-assembled",
            note=f"Proposed Tier {result.tier}",
        )
    return assessment_out(db, t, assessment, reassembly)


def confirm(db: Session, user: User, t: Transition, body: TierConfirmIn) -> TierAssessmentOut:
    """IRM confirms or changes the tier (caller commits)."""
    ensure_transition_role(db, user, t, Perm.CONFIRM_TIER)
    assessment = scope_domain.get_assessment(db, t.id)
    if assessment is None or assessment.proposed_tier is None:
        raise Conflict("No tier proposed yet")
    changed = body.tier != assessment.proposed_tier
    reason = (body.reason or "").strip()
    if changed and not reason:
        raise BadRequest("Reason required to change the tier")

    previous_applied = scope_domain.applied_tier(db, t)
    before = audit.snapshot(assessment, TIER_FIELDS)
    assessment.confirmed_tier = body.tier
    assessment.confirmed_by_irm = user.id
    assessment.confirmed_by_or_focal = assessment.proposed_by
    assessment.confirmed_at = clock.now()
    assessment.change_reason = reason if changed else None
    t.risk_tier = body.tier
    t.tier_status = "Confirmed"
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="TierAssessment",
        entity_id=t.id,
        action="Tier changed" if changed else "Tier confirmed",
        transition_id=t.id,
        before=before,
        after=audit.snapshot(assessment, TIER_FIELDS),
        note=(
            f"Tier {assessment.proposed_tier} -> Tier {body.tier}: {reason}"
            if changed
            else f"Confirmed Tier {body.tier}"
        ),
    )
    reassembly = None
    if t.assessment_launched_at is not None and previous_applied != body.tier:
        reassembly = scope_domain.reassemble_transition(
            db,
            t,
            user,
            action="Checklist re-assembled",
            note=f"Tier {previous_applied} -> Tier {body.tier}",
        )
    return assessment_out(db, t, assessment, reassembly)


# --- AI profile ----------------------------------------------------------------------------------


def _profile(db: Session, transition_id: str) -> AIProfile | None:
    return db.scalar(select(AIProfile).where(AIProfile.transition_id == transition_id))


def profile_out(db: Session, t: Transition) -> AIProfileOut:
    profile = _profile(db, t.id)
    if profile is None:
        return AIProfileOut(transition_id=t.id)
    return AIProfileOut(
        transition_id=t.id,
        updated_at=profile.updated_at,
        **{f: getattr(profile, f) for f in AI_PROFILE_FIELDS},
    )


def save_profile(db: Session, user: User, t: Transition, body: AIProfileIn) -> AIProfileOut:
    ensure_transition_role(db, user, t, Perm.EDIT_AI_PROFILE)
    require_ai_flavour(db, t, "AI profile applies to AI project types only")
    profile = _profile(db, t.id)
    before = audit.snapshot(profile, AI_PROFILE_FIELDS) if profile is not None else None
    if profile is None:
        profile = AIProfile(transition_id=t.id)
        db.add(profile)
    for field in AI_PROFILE_FIELDS:
        setattr(profile, field, getattr(body, field))
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="AIProfile",
        entity_id=t.id,
        action="AI profile updated",
        transition_id=t.id,
        before=before,
        after=audit.snapshot(profile, AI_PROFILE_FIELDS),
    )
    return profile_out(db, t)
