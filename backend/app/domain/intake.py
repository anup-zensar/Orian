"""Intake: create / edit transitions, ServiceNow prefill, autonomous mode (FR-020, FR-081; AC-05).

Validation produces one reason per problem (422 ``reasons``). Option lists come from reference data
(intake options, regions), ``FlavourRule`` (project types) and ``Portfolio``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import ensure_admin_or_assigned, ensure_open, ensure_transition_role
from app.deps import ensure
from app.domain import audit
from app.domain import scope as scope_domain
from app.domain.ids import next_id
from app.domain.tiering import reference
from app.errors import BadRequest, Conflict, Forbidden, NotFound
from app.models import FlavourRule, Portfolio, Transition, User
from app.permissions import Perm
from app.rules.constants import ACTOR_HUMAN
from app.schemas.intake import (
    ServiceNowProjectOut,
    TransitionCreateIn,
    TransitionUpdateIn,
)
from app.services.factory import get_servicenow_service

RETAIL_PORTFOLIO = "Retail Site Systems"
AI_REQUIRED_FIELDS = ("audience", "write_actions", "sensitive_data")
OPTION_FIELDS = (
    "audience",
    "write_actions",
    "sensitive_data",
    "target_gate",
    "investment_type",
    "delivery_method",
)
FIELD_LABELS = {
    "name": "Solution / transition name",
    "project_type": "Project type",
    "portfolio": "Portfolio",
    "region": "Region",
    "or_focal_user_id": "OR focal",
    "audience": "Audience",
    "write_actions": "Write actions",
    "sensitive_data": "Sensitive data",
}
# Role pickers: Transition column -> (required user role, label)
ROLE_FIELDS: dict[str, tuple[str, str]] = {
    "or_focal_user_id": ("OR_FOCAL", "OR focal"),
    "pm_user_id": ("PM", "Project manager"),
    "architect_user_id": ("ARCHITECT", "Architect"),
    "olm_user_id": ("OLM", "OLM"),
    "irm_user_id": ("IRM", "IRM"),
}
# PATCH field groups (BE#2): who may change what.
DESCRIPTIVE_FIELDS = (
    "name",
    "servicenow_project_id",
    "portfolio",
    "region",
    "market",
    "sites",
    "target_gate",
    "investment_type",
    "delivery_method",
    "description",
    "next_decision_date",
    "blocker_note",
)
ASSIGN_LOW_FIELDS = ("pm_user_id", "architect_user_id", "olm_user_id")  # the OR focal (or an Admin)
ASSIGN_HIGH_FIELDS = ("or_focal_user_id", "irm_user_id")  # Admin only
TIER_ANSWER_FIELDS = (
    "audience",
    "write_actions",
    "sensitive_data",
)  # changing them voids a proposal
TIER_INPUT_FIELDS = (*TIER_ANSWER_FIELDS, "project_type")  # OR focal only, locked once confirmed
EDITABLE_FIELDS = (
    *DESCRIPTIVE_FIELDS,
    *TIER_INPUT_FIELDS,
    *ASSIGN_HIGH_FIELDS,
    *ASSIGN_LOW_FIELDS,
)
REQUIRED_FIELDS = ("name", "project_type", "portfolio", "region", "or_focal_user_id")
AUDIT_FIELDS = (*EDITABLE_FIELDS, "current_gate", "status", "autonomous_mode")


# --- helpers -------------------------------------------------------------------------------------


def get_transition(db: Session, transition_id: str) -> Transition:
    t = db.get(Transition, transition_id)
    if t is None:
        raise NotFound("Transition not found")
    return t


def _clean(value: Any) -> Any:
    """Trim strings; blank -> None."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _normalise_sites(raw: list[dict[str, str]], portfolio: str | None) -> list[dict[str, str]]:
    """Sites are only kept for Retail Site Systems."""
    return [dict(row) for row in raw] if portfolio == RETAIL_PORTFOLIO else []


def _validate(
    db: Session,
    values: dict[str, Any],
    touched: set[str],
    *,
    raw_sites: list[dict[str, str]],
) -> list[str]:
    """Reasons for the merged ``values``; only ``touched`` fields get option / conditional checks
    (so unrelated edits on legacy seeded rows never fail)."""
    reasons: list[str] = []
    ref = reference(db)
    options = ref.get("intake_options", {})

    for field in REQUIRED_FIELDS:
        if field in touched and not values.get(field):
            reasons.append(f"{FIELD_LABELS[field]} is required")

    project_types = [r.project_type for r in db.scalars(select(FlavourRule))]
    portfolios = [p.name for p in db.scalars(select(Portfolio))]
    project_type = values.get("project_type")
    if project_type and "project_type" in touched and project_type not in project_types:
        reasons.append(f"Project type '{project_type}' is not one of: {', '.join(project_types)}")
    if values.get("portfolio") and "portfolio" in touched and values["portfolio"] not in portfolios:
        reasons.append(f"Portfolio '{values['portfolio']}' is not one of: {', '.join(portfolios)}")
    regions = ref.get("regions", [])
    if values.get("region") and "region" in touched and regions and values["region"] not in regions:
        reasons.append(f"Region '{values['region']}' is not one of: {', '.join(regions)}")
    for field in OPTION_FIELDS:
        allowed = options.get(field, [])
        value = values.get(field)
        if field in touched and value is not None and allowed and value not in allowed:
            reasons.append(f"{field} '{value}' is not one of: {', '.join(allowed)}")

    needs_ai_fields = (
        project_type in project_types
        and bool(touched & {"project_type", *AI_REQUIRED_FIELDS})
        and scope_domain.requires_tiering(db, project_type)
    )
    if needs_ai_fields:
        for field in AI_REQUIRED_FIELDS:
            if not values.get(field):
                reasons.append(f"{FIELD_LABELS[field]} is required for {project_type}")

    if values.get("portfolio") == RETAIL_PORTFOLIO and touched & {"portfolio", "sites"}:
        if not raw_sites:
            reasons.append("Add at least one site (Site ID and Site key) for Retail Site Systems")
        for index, row in enumerate(raw_sites, start=1):
            if not row["site_id"] or not row["site_key"]:
                reasons.append(f"Site row {index}: both Site ID and Site key are required")

    for field, (role, label) in ROLE_FIELDS.items():
        user_id = values.get(field)
        if field not in touched or not user_id:
            continue
        user = db.get(User, user_id)
        if user is None:
            reasons.append(f"{label}: unknown user '{user_id}'")
        elif user.role != role:
            reasons.append(f"{label}: {user.name} does not have the {role} role")
    return reasons


def _default_role_user(db: Session, role: str) -> str | None:
    return db.scalar(select(User.id).where(User.role == role).order_by(User.id))


# --- create --------------------------------------------------------------------------------------


def create_transition(db: Session, user: User, body: TransitionCreateIn) -> Transition:
    ensure(user, Perm.CREATE_TRANSITION)
    data = body.model_dump()
    confirm_duplicate = data.pop("confirm_duplicate", False)
    values: dict[str, Any] = {k: _clean(v) for k, v in data.items() if k != "sites"}
    # An OR focal creates only transitions they will own (default: themselves); PM / Admin pick any.
    if user.role == "OR_FOCAL":
        if not values.get("or_focal_user_id"):
            values["or_focal_user_id"] = user.id
        elif values["or_focal_user_id"] != user.id:
            raise Forbidden(
                "An OR focal can only create transitions they will own - pick yourself as OR focal"
            )
    values["market"] = values.get("market") or ""
    if values.get("servicenow_project_id"):
        values["servicenow_project_id"] = str(values["servicenow_project_id"]).upper()
    values["description"] = (data.get("description") or "").strip()
    for field, (role, _label) in ROLE_FIELDS.items():
        if field != "or_focal_user_id" and field not in body.model_fields_set:
            values[field] = _default_role_user(db, role)
    raw_sites = _normalise_sites_raw(data["sites"])
    reasons = _validate(db, values, set(EDITABLE_FIELDS), raw_sites=raw_sites)
    if reasons:
        raise BadRequest("Validation failed", reasons)

    duplicate = (
        db.scalars(
            select(Transition.id).where(
                Transition.servicenow_project_id == values["servicenow_project_id"],
                Transition.status == "Active",
            )
        ).first()
        if values.get("servicenow_project_id")
        else None
    )
    if duplicate and not confirm_duplicate:
        raise Conflict(
            "A transition already exists for this ServiceNow project",
            [
                f"{duplicate} is already active for {values['servicenow_project_id']} - open it, "
                "or confirm to create a second transition for the same project"
            ],
        )

    t = Transition(
        id=next_id(db, Transition.id, "TR-"),
        current_gate="SG0",
        status="Active",
        autonomous_mode=False,
        assessment_launched_at=None,
        scope_decisions={},
        created_by=user.id,
        is_flagship=False,
        **{
            k: values.get(k)
            for k in EDITABLE_FIELDS
            if k not in ("sites", "blocker_note", "description", "market")
        },
        description=values["description"],
        market=values["market"],
        sites=_normalise_sites(raw_sites, values["portfolio"]),
    )
    db.add(t)
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=t.id,
        action="Transition created",
        transition_id=t.id,
        after=audit.snapshot(t, AUDIT_FIELDS),
        note=f"{t.project_type} / {t.portfolio} / {t.region}",
    )
    return t


def _normalise_sites_raw(raw: Any) -> list[dict[str, str]]:
    """Trimmed rows with fully blank rows dropped (validation sees the rows the user typed)."""
    rows: list[dict[str, str]] = []
    for row in raw or []:
        site_id = str(row.get("site_id") or "").strip()
        site_key = str(row.get("site_key") or "").strip()
        if site_id or site_key:
            rows.append({"site_id": site_id, "site_key": site_key})
    return rows


# --- update --------------------------------------------------------------------------------------


def _person_name(db: Session, user_id: str | None) -> str:
    person = db.get(User, user_id) if user_id else None
    return person.name if person is not None else "none"


def _check_update_access(
    db: Session,
    user: User,
    t: Transition,
    values: dict[str, Any],
    sent: set[str],
    raw_sites: list[dict[str, str]],
) -> None:
    """Per-group access of PATCH (BE#2). Only fields whose value really changes are checked."""
    changing = {f for f in sent - {"sites"} if values[f] != getattr(t, f)}
    if "sites" in sent and _normalise_sites(raw_sites, values["portfolio"]) != (t.sites or []):
        changing.add("sites")  # sites are workflow data: an Admin may not edit them (A-75)
    people = set(ASSIGN_LOW_FIELDS) | set(ASSIGN_HIGH_FIELDS)
    if user.role == "ADMIN" and changing - people:
        # R-01: an Admin may re-assign people and configure, never edit workflow data (dates, blocker
        # note, target gate, description ...) - those belong to the OR focal of the transition.
        ensure_transition_role(db, user, t, Perm.EDIT_TRANSITION, phrase="edit this transition")
    ensure_admin_or_assigned(db, user, t, Perm.EDIT_TRANSITION, phrase="edit this transition")
    if changing & set(ASSIGN_HIGH_FIELDS) and user.role != "ADMIN":
        raise Forbidden(
            f"Only an Admin can change the OR focal or IRM of {t.id} - an OR focal cannot pick "
            "who confirms the tier or hand the transition away"
        )
    if changing & set(TIER_INPUT_FIELDS):
        # Admin has no workflow rights: the tier inputs belong to the OR focal who proposes the tier.
        ensure_transition_role(
            db, user, t, Perm.PROPOSE_TIER, phrase="change the tier inputs of this transition"
        )
        if t.tier_status == "Confirmed":
            raise Conflict(
                "Tier inputs are locked",
                [
                    f"Tier inputs are locked after the IRM confirmed Tier {t.risk_tier} - "
                    "ask the IRM to change the tier (Tiering page, Change tier with a reason)"
                ],
            )


def _clear_tier_proposal(db: Session, user: User, t: Transition) -> None:
    """Tier inputs changed while the tier was only proposed: the proposal no longer matches, so it is
    cleared and the OR focal proposes again (the IRM never confirms stale answers)."""
    assessment = scope_domain.get_assessment(db, t.id)
    if assessment is None or assessment.proposed_tier is None or t.tier_status != "Proposed":
        return
    old = assessment.proposed_tier
    assessment.proposed_tier = None
    assessment.rationale = []
    assessment.proposed_by = None
    t.risk_tier = None
    t.tier_status = None
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="TierAssessment",
        entity_id=t.id,
        action="Tier proposal cleared",
        transition_id=t.id,
        before={"proposed_tier": old},
        after={"proposed_tier": None},
        note=f"Tier inputs changed - the proposed Tier {old} must be proposed again",
    )
    if t.assessment_launched_at is not None:
        scope_domain.reassemble_transition(
            db,
            t,
            user,
            action="Checklist re-assembled",
            note=f"Proposed Tier {old} cleared",
        )


def update_transition(db: Session, user: User, t: Transition, body: TransitionUpdateIn) -> None:
    sent = {f for f in body.model_fields_set if f in EDITABLE_FIELDS}
    data = body.model_dump()

    values: dict[str, Any] = {f: getattr(t, f) for f in EDITABLE_FIELDS}
    for field in sent - {"sites"}:
        value = _clean(data[field])
        if field in ("description", "market"):
            value = (data[field] or "").strip()
        if field == "servicenow_project_id" and value:
            value = str(value).upper()
        values[field] = value
    if "sites" in sent:
        raw_sites = _normalise_sites_raw(data["sites"])
    else:
        raw_sites = _normalise_sites_raw(t.sites)

    _check_update_access(db, user, t, values, sent, raw_sites)
    ensure_open(t)

    reasons = _validate(db, values, sent, raw_sites=raw_sites)
    if reasons:
        raise BadRequest("Validation failed", reasons)

    before = audit.snapshot(t, AUDIT_FIELDS)
    old_flavour = (t.project_type, t.portfolio)
    changed: list[str] = []
    people: list[str] = []
    for field in sent:
        new_value = (
            _normalise_sites(raw_sites, values["portfolio"]) if field == "sites" else values[field]
        )
        old_value = getattr(t, field)
        if old_value != new_value:
            if field in ROLE_FIELDS:
                people.append(
                    f"{ROLE_FIELDS[field][1]}: {_person_name(db, old_value)} -> "
                    f"{_person_name(db, new_value)}"
                )
            setattr(t, field, new_value)
            changed.append(field)
    if "portfolio" in changed and "sites" not in sent and t.portfolio != RETAIL_PORTFOLIO:
        t.sites = []
        changed.append("sites")
    if not changed:
        return
    db.flush()
    note = "Changed: " + ", ".join(changed)
    if people:
        note += " (" + "; ".join(people) + ")"
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=t.id,
        action="Transition updated",
        transition_id=t.id,
        before=before,
        after=audit.snapshot(t, AUDIT_FIELDS),
        note=note,
    )
    if set(changed) & set(TIER_ANSWER_FIELDS):
        _clear_tier_proposal(db, user, t)
    if t.assessment_launched_at is not None and (t.project_type, t.portfolio) != old_flavour:
        scope_domain.reassemble_transition(
            db,
            t,
            user,
            action="Checklist re-assembled",
            note=(f"{old_flavour[0]} / {old_flavour[1]} -> {t.project_type} / {t.portfolio}"),
        )


# --- autonomous mode -----------------------------------------------------------------------------


def set_autonomous_mode(db: Session, user: User, t: Transition, enabled: bool) -> None:
    ensure_transition_role(db, user, t, Perm.TOGGLE_AUTONOMOUS)
    if t.autonomous_mode == enabled:
        return
    before = {"autonomous_mode": t.autonomous_mode}
    t.autonomous_mode = enabled
    db.flush()
    audit.record(
        db,
        actor=user,
        actor_type=ACTOR_HUMAN,
        entity="Transition",
        entity_id=t.id,
        action=f"Autonomous mode {'on' if enabled else 'off'}",
        transition_id=t.id,
        before=before,
        after={"autonomous_mode": enabled},
    )


# --- ServiceNow ----------------------------------------------------------------------------------


def lookup_servicenow(db: Session, project_id: str) -> ServiceNowProjectOut:
    wanted = (project_id or "").strip().upper()
    record = get_servicenow_service().get_project(wanted)
    if record is None:
        raise NotFound("Not found in ServiceNow (mock) – enter manually")
    pm_name = record.get("pm")
    pm_user_id: str | None = None
    if pm_name:
        for u in db.scalars(select(User).where(User.role == "PM").order_by(User.id)):
            if u.name.strip().lower() == str(pm_name).strip().lower():
                pm_user_id = u.id
                break
    return ServiceNowProjectOut(
        project_id=str(record.get("project_id") or wanted),
        name=record.get("name") or "",
        project_type=record.get("project_type"),
        investment_type=record.get("investment_type"),
        delivery_method=record.get("delivery_method"),
        portfolio=record.get("portfolio"),
        region=record.get("region"),
        market=record.get("market"),
        description=record.get("description") or "",
        pm_name=pm_name,
        pm_user_id=pm_user_id,
    )
