"""Intake: create / get / patch transitions, autonomous mode (spec §8.4, §9; FR-020, FR-030). M3."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require
from app.models import User
from app.permissions import Perm
from app.schemas.intake import (
    AutonomousModeIn,
    TransitionCreateIn,
    TransitionDetailOut,
    TransitionUpdateIn,
)

router = APIRouter(tags=["intake"], dependencies=[Depends(get_current_user)])


@router.post("/transitions", response_model=TransitionDetailOut, status_code=201)
def create_transition(
    body: TransitionCreateIn,
    user: User = Depends(require(Perm.CREATE_TRANSITION)),
    db: Session = Depends(get_db),
) -> TransitionDetailOut:
    """Create a transition from the intake form (spec §8.4, FR-020). OR focal / PM / Admin only (403).

    Validations (422 with one reason per problem, listed in ``reasons``):
    - project_type, portfolio, region, audience, write_actions, sensitive_data, target_gate,
      investment_type, delivery_method must be active options of the configuration (Admin: Project
      types, Portfolios, Forms & dropdowns).
    - Fields the Admin required for the project type (by default audience, write_actions and
      sensitive_data for the AI project types) are required, as are required custom fields.
    - ``custom_fields`` ({"cf_<key>": value}) holds the "Additional details" fields of the form; every
      key must be an active custom field and its value is checked against the field type, range and
      dropdown list. A blank value clears the field.
    - Portfolio with "Requires sites" (AC-05, Retail Site Systems by default): at least one ``sites``
      row and every row must have both Site ID and Site key (trimmed, non-empty). Fully blank rows are
      dropped first; for other portfolios sites are ignored (stored as []).
    - or_focal_user_id is required; every role picker must reference an existing user whose role matches
      (or_focal -> OR_FOCAL, pm -> PM, architect -> ARCHITECT, olm -> OLM, irm -> IRM).
    - name is trimmed and non-empty.

    Behaviour: new id = ``app.domain.ids.next_id(db, Transition.id, "TR-")``; current_gate "SG0";
    status Active; autonomous_mode False; no items yet (assessment_launched_at None, scope_decisions
    {}); created_by = current user; no TierAssessment row yet. Audit event "Transition created" with
    actor source Human. Returns the full detail (201). The UI continues to the tiering wizard when
    ``requires_tiering`` else to the Scope page.
    """
    from app.domain import intake as intake_domain
    from app.domain.transition_detail import build_transition_detail

    t = intake_domain.create_transition(db, user, body)
    db.commit()
    return build_transition_detail(db, t, user)


@router.get("/transitions/{transition_id}", response_model=TransitionDetailOut)
def get_transition(
    transition_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransitionDetailOut:
    """Full detail for the workspace header, overview lens cards and stepper (spec §8.7).

    404 "Transition not found" for an unknown id. Any signed-in role may read.
    Built with ``app.domain.transition_detail.build_transition_detail``.
    """
    from app.domain import intake as intake_domain
    from app.domain.transition_detail import build_transition_detail

    return build_transition_detail(db, intake_domain.get_transition(db, transition_id), user)


@router.patch("/transitions/{transition_id}", response_model=TransitionDetailOut)
def update_transition(
    transition_id: str,
    body: TransitionUpdateIn,
    user: User = Depends(require(Perm.EDIT_TRANSITION)),
    db: Session = Depends(get_db),
) -> TransitionDetailOut:
    """Edit intake fields (only fields present in the body, via ``model_fields_set``).

    403 unless the transition's own OR focal (Perm.EDIT_TRANSITION; Admin may edit and re-assign); the
    OR focal / IRM can only be re-assigned by an Admin; tier inputs (audience, write actions, sensitive
    data, project type) only by the OR focal and are locked (409) once the IRM confirmed the tier (before
    that a change clears the tier proposal); 404 unknown id; 409 "Transition is closed" when status is
    Closed; 422 with the same option / role / site / custom-field validations as create, evaluated on the merged
    result (a field explicitly set to null clears an optional field; required fields cannot be null).

    BR-010 re-assembly: if the assessment is launched and project_type or portfolio changes, rebuild
    the plan with ``rules.checklist.assemble_checklist`` (library = active PlaybookItems, flavour
    checklists from FlavourRule of the new type, tier = confirmed or proposed tier, roles of the
    transition) and persist ``rules.checklist.reassemble(existing, planned, library)`` (added items are
    created, excluded ones become Not applicable with excluded_by, existing statuses/evidence/notes of
    items that still apply are kept, a human's own N/A is never overridden). Switching to a type that
    requires tiering without a tier assessment keeps tier None (all AI items apply, A-35). Audit event
    with the re-assembly counts {added, excluded, restored}. A change of pm/architect/olm/irm does not
    reassign existing item owners. Before launch only the fields change. Audit Human for every edit with
    the changed field names in the note.
    """
    from app.domain import intake as intake_domain
    from app.domain.transition_detail import build_transition_detail

    t = intake_domain.get_transition(db, transition_id)
    intake_domain.update_transition(db, user, t, body)
    db.commit()
    return build_transition_detail(db, t, user)


@router.post("/transitions/{transition_id}/autonomous-mode", response_model=TransitionDetailOut)
def set_autonomous_mode(
    transition_id: str,
    body: AutonomousModeIn,
    user: User = Depends(require(Perm.TOGGLE_AUTONOMOUS)),
    db: Session = Depends(get_db),
) -> TransitionDetailOut:
    """Turn autonomous mode on/off (FR-081): when on, Orion may auto-send Chaser / Reminder /
    Input request drafts but never Approval request or Leadership update (BR-050).

    403 without TOGGLE_AUTONOMOUS; 404 unknown id. Idempotent when the value is unchanged (no audit).
    Audit event Human "Autonomous mode on/off".
    """
    from app.domain import intake as intake_domain
    from app.domain.transition_detail import build_transition_detail

    t = intake_domain.get_transition(db, transition_id)
    intake_domain.set_autonomous_mode(db, user, t, body.enabled)
    db.commit()
    return build_transition_detail(db, t, user)
